/**
 * Stock tab — a paginated, incrementally-saved, relational inventory worksheet.
 *
 * Left rail selects the view:
 *   - "All medications" -> the whole inventory, loaded a page at a time
 *     ("Load more" appends the next page; header shows "showing X of TOTAL")
 *   - a single medication (listed alphabetically, grouped by starting letter)
 *     -> all of that drug's rows across locations
 *
 * The backend is relational (one row = one InventoryItem with a numeric id).
 * Editing is INCREMENTAL: each inline cell edit PATCHes just that row (or POSTs
 * a brand-new row), never a full-sheet PUT. Right-clicking a row opens a context
 * menu with per-drug summaries (total on hand, days of supply, per-location
 * breakdown), row metadata, and delete. Loaded pages are cached (cache.ts) so
 * returning to the tab — or re-selecting a drug — is instant.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import DataGrid from '../components/DataGrid/DataGrid'
import type { GridColumn, Row } from '../components/DataGrid/xlsx'
import {
  listStock,
  patchRow,
  addRow,
  deleteRow,
  bulkReplace,
  getSummary,
  type DrugSummary,
} from '../api/stock'
import { cached, getCache, invalidate } from '../cache'
import { C } from '../theme'

const COLUMNS: GridColumn[] = [
  { key: 'drug', name: 'Drug', width: 170 },
  { key: 'location', name: 'Location', width: 160 },
  { key: 'on_hand', name: 'On hand', width: 100 },
  { key: 'unit', name: 'Unit', width: 90 },
  { key: 'expiry_date', name: 'Expiry', width: 120 },
  { key: 'avg_daily_use', name: 'Avg daily use', width: 130 },
  { key: 'supplier', name: 'Supplier', width: 150 },
  { key: 'last_delivery', name: 'Last delivery', width: 130 },
]

/** Only the persisted business fields (never id / created_at / etc). */
const FIELD_KEYS = COLUMNS.map((c) => c.key)

const emptyRow = (): Row => ({
  drug: '', location: '', on_hand: '', unit: '', expiry_date: '', avg_daily_use: '', supplier: '', last_delivery: '',
})

const isBlank = (r: Row) => FIELD_KEYS.every((k) => r[k] === '' || r[k] == null)

const AGG = 'ALL'
const PAGE = 200

const BASE = import.meta.env.VITE_API_URL || ''

/** Row id -> number, or null when the row hasn't been persisted yet. */
function rowId(r: Row): number | null {
  const v = r.id
  if (v === '' || v == null) return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

/** Just the persisted fields of a row, for PATCH/POST bodies. */
function fieldsOf(r: Row): Row {
  const out: Row = {}
  for (const k of FIELD_KEYS) out[k] = r[k] ?? ''
  return out
}

interface MedRef { drug: string; total_on_hand?: number; rows?: number; locations?: number }

/** All distinct medications for the rail — the no-arg summary endpoint. */
async function fetchMeds(): Promise<MedRef[]> {
  const res = await fetch(`${BASE}/api/v1/stock/summary`)
  if (!res.ok) throw new Error(`summary -> ${res.status}`)
  const data = await res.json()
  return (data.items ?? []) as MedRef[]
}

type Status = 'loading' | 'saved' | 'saving' | 'offline'
const STATUS_TEXT: Record<Status, { label: string; color: string }> = {
  loading: { label: 'Loading…', color: C.muted },
  saved: { label: 'Saved to database', color: C.teal },
  saving: { label: 'Saving…', color: C.amber },
  offline: { label: 'Offline — backend not reachable', color: C.red },
}

type MenuState = { row: Row; drug: string; x: number; y: number }
type PanelState = { title: string; x: number; y: number; kind: 'summary' | 'meta'; summary?: DrugSummary; row?: Row }

export default function Stock() {
  const [selected, setSelected] = useState<string>(AGG)
  const [meds, setMeds] = useState<MedRef[]>(() => getCache<MedRef[]>('stock:meds') ?? [])
  const [status, setStatus] = useState<Status>('loading')

  // "All medications" paginated view.
  const [allRows, setAllRows] = useState<Row[]>([])
  const [allTotal, setAllTotal] = useState(0)
  const [allOffset, setAllOffset] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)

  // Single-drug view.
  const [drugRows, setDrugRows] = useState<Row[]>([])

  const [menu, setMenu] = useState<MenuState | null>(null)
  const [panel, setPanel] = useState<PanelState | null>(null)

  const isAll = selected === AGG
  const displayed = isAll ? allRows : drugRows

  // Whether the current view already holds persisted (id-bearing) rows. Used to
  // safely recognise a file import (a wholesale replacement of populated data
  // with id-less rows) without mistaking hand-typed new rows for one.
  const viewHasIds = useRef(false)
  useEffect(() => { viewHasIds.current = displayed.some((r) => rowId(r) != null) }, [displayed])

  // Load the medication index for the rail (cached).
  useEffect(() => {
    let alive = true
    cached('stock:meds', fetchMeds)
      .then((m) => { if (alive) setMeds(m) })
      .catch(() => { /* rail just stays empty; grid load reports offline */ })
    return () => { alive = false }
  }, [])

  // Load the first page of "All medications" (cached under stock:all:page0).
  const loadAllFirstPage = useCallback(() => {
    setStatus('loading')
    cached('stock:all:page0', () => listStock({ limit: PAGE, offset: 0 }))
      .then((page) => {
        setAllRows(page.items)
        setAllTotal(page.total)
        setAllOffset(page.items.length)
        setStatus('saved')
      })
      .catch(() => setStatus('offline'))
  }, [])

  // Load every row for a single drug (small; cached per drug).
  const loadDrug = useCallback((drug: string) => {
    setStatus('loading')
    cached(`stock:drug:${drug}`, () => listStock({ drug, limit: 2000 }))
      .then((page) => {
        setDrugRows(page.items)
        setStatus('saved')
      })
      .catch(() => setStatus('offline'))
  }, [])

  useEffect(() => {
    if (isAll) loadAllFirstPage()
    else loadDrug(selected)
    // switching view closes any open overlay
    setMenu(null)
    setPanel(null)
  }, [selected, isAll, loadAllFirstPage, loadDrug])

  const loadMore = useCallback(() => {
    if (loadingMore || allRows.length >= allTotal) return
    setLoadingMore(true)
    listStock({ limit: PAGE, offset: allOffset })
      .then((page) => {
        setAllRows((prev) => [...prev, ...page.items])
        setAllOffset((o) => o + page.items.length)
        setAllTotal(page.total)
      })
      .catch(() => setStatus('offline'))
      .finally(() => setLoadingMore(false))
  }, [loadingMore, allRows.length, allTotal, allOffset])

  // Alphabetical medication index, grouped by starting letter.
  const grouped = useMemo(() => {
    const g: Record<string, Set<string>> = {}
    meds.forEach((m) => {
      const drug = String(m.drug || '').trim()
      if (!drug) return
      const L = drug[0].toUpperCase()
      ;(g[L] ||= new Set()).add(drug)
    })
    const out: Record<string, string[]> = {}
    Object.keys(g).forEach((L) => (out[L] = [...g[L]].sort()))
    return out
  }, [meds])

  // Drop cached pages after any write so the tab reloads fresh next time.
  const bust = useCallback(() => {
    invalidate('stock:all')
    invalidate('stock:drug')
    invalidate('stock:meds')
  }, [])

  /** Replace a row object in the current view's local state (by reference or id). */
  const patchLocal = useCallback((target: Row, next: Row) => {
    const setter = isAll ? setAllRows : setDrugRows
    setter((prev) => prev.map((r) => (r === target || (rowId(r) != null && rowId(r) === rowId(target)) ? next : r)))
  }, [isAll])

  const removeLocal = useCallback((id: number) => {
    setAllRows((prev) => prev.filter((r) => rowId(r) !== id))
    setDrugRows((prev) => prev.filter((r) => rowId(r) !== id))
    setAllTotal((t) => Math.max(0, t - 1))
  }, [])

  // Keep the displayed grid in sync (edits, paste, add-row, clear).
  // Genuine bulk imports (a fresh sheet where nothing has an id) go through
  // bulkReplace — note that PUT replaces the ENTIRE inventory.
  const handleRowsChange = useCallback(
    (next: Row[]) => {
      const clean = next.filter((r) => !isBlank(r))
      if (isAll) setAllRows(clean)
      else setDrugRows(clean)

      // A file import replaces a populated sheet with brand-new (id-less) rows.
      // Hand-typing a new row into an empty view must NOT trigger a full PUT.
      const looksLikeImport = viewHasIds.current && clean.length > 0 && clean.every((r) => rowId(r) == null)
      if (looksLikeImport) {
        setStatus('saving')
        bulkReplace(clean.map(fieldsOf))
          .then(() => { bust(); setStatus('saved'); if (isAll) loadAllFirstPage(); else loadDrug(selected) })
          .catch(() => setStatus('offline'))
      }
    },
    [isAll, selected, bust, loadAllFirstPage, loadDrug],
  )

  // Incremental save: PATCH an existing row, POST a brand-new one.
  const handleCellEdited = useCallback(
    async (row: Row) => {
      if (isBlank(row)) return
      const id = rowId(row)
      setStatus('saving')
      try {
        if (id != null) {
          const saved = await patchRow(id, fieldsOf(row))
          patchLocal(row, { ...row, ...saved })
        } else {
          const created = await addRow(fieldsOf(row))
          patchLocal(row, { ...row, ...created })
        }
        bust()
        setStatus('saved')
      } catch {
        setStatus('offline')
      }
    },
    [patchLocal, bust],
  )

  // Right-click -> context menu for the row under the cursor.
  const handleContextMenu = useCallback((row: Row, x: number, y: number) => {
    setPanel(null)
    setMenu({ row, drug: String(row.drug || '').trim(), x, y })
  }, [])

  // Close menu/panel on outside click or Escape.
  useEffect(() => {
    if (!menu && !panel) return
    const onDown = () => { setMenu(null); setPanel(null) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { setMenu(null); setPanel(null) } }
    // Delay so the opening click doesn't immediately close it.
    const t = setTimeout(() => window.addEventListener('mousedown', onDown), 0)
    window.addEventListener('keydown', onKey)
    return () => { clearTimeout(t); window.removeEventListener('mousedown', onDown); window.removeEventListener('keydown', onKey) }
  }, [menu, panel])

  const showSummary = useCallback(async (drug: string, x: number, y: number, title: string) => {
    setMenu(null)
    setStatus('loading')
    try {
      const summary = await getSummary(drug)
      setPanel({ title, x, y, kind: 'summary', summary })
      setStatus('saved')
    } catch {
      setStatus('offline')
    }
  }, [])

  const onDeleteRow = useCallback(async (row: Row) => {
    setMenu(null)
    const id = rowId(row)
    if (id == null) return
    setStatus('saving')
    try {
      await deleteRow(id)
      removeLocal(id)
      bust()
      setStatus('saved')
    } catch {
      setStatus('offline')
    }
  }, [removeLocal, bust])

  const s = STATUS_TEXT[status]

  const railItem = (name: string, active: boolean, onClick: () => void, sub?: string) => (
    <button
      key={name}
      onClick={onClick}
      style={{
        display: 'block', width: '100%', textAlign: 'left',
        background: active ? C.panelAlt : 'transparent',
        border: `1px solid ${active ? C.teal : 'transparent'}`,
        borderRadius: 7, padding: '8px 10px',
        color: active ? C.text : C.muted, fontSize: 12.5, fontWeight: active ? 600 : 400, cursor: 'pointer',
      }}
    >
      {name}
      {sub && <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>{sub}</div>}
    </button>
  )

  const allSub = allTotal ? `${allRows.length} of ${allTotal} rows` : `${allRows.length} rows`

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
      {/* Left rail: view + medication index */}
      <aside style={{ width: 232, flexShrink: 0, borderRight: `1px solid ${C.border}`, background: C.panel, overflowY: 'auto', padding: 12 }}>
        <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '2px 0 8px' }}>VIEW</div>
        {railItem('All medications', isAll, () => setSelected(AGG), allSub)}

        <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '14px 0 6px' }}>MEDICATIONS</div>
        {Object.keys(grouped).sort().map((letter) => (
          <div key={letter} style={{ marginBottom: 6 }}>
            <div className="disp" style={{ fontSize: 11, color: C.muted2, padding: '2px 10px' }}>{letter}</div>
            {grouped[letter].map((drug) => railItem(drug, selected === drug, () => setSelected(drug)))}
          </div>
        ))}
      </aside>

      {/* Right: header + grid */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 16px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <div className="disp" style={{ fontSize: 17, fontWeight: 700 }}>
            Stock — {isAll ? 'All medications' : selected}
          </div>
          <div style={{ fontSize: 12, color: C.muted }}>
            Edits save per-row to the database. Right-click a row for summaries.
          </div>
          <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.color, display: 'inline-block' }} />
            <span className="mono" style={{ fontSize: 11, color: s.color }}>{s.label}</span>
          </span>
        </div>

        {isAll && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="mono" style={{ fontSize: 11, color: C.muted2 }}>
              showing {allRows.length} of {allTotal}
            </span>
            {allRows.length < allTotal && (
              <button
                onClick={loadMore}
                disabled={loadingMore}
                style={{
                  background: C.panelAlt, color: C.text, border: `1px solid ${C.border}`,
                  borderRadius: 6, padding: '4px 10px', fontSize: 11.5,
                  cursor: loadingMore ? 'default' : 'pointer', opacity: loadingMore ? 0.6 : 1,
                }}
              >
                {loadingMore ? 'Loading…' : `Load more (${PAGE})`}
              </button>
            )}
          </div>
        )}

        <div style={{ flex: 1, minHeight: 0 }}>
          <DataGrid
            key={selected}
            columns={COLUMNS}
            rows={displayed}
            onRowsChange={handleRowsChange}
            onCellEdited={handleCellEdited}
            onContextMenu={handleContextMenu}
            getRowId={(r) => Number(r.id)}
            name={isAll ? 'stock' : `stock-${selected.split(' ')[0].toLowerCase()}`}
            emptyRow={emptyRow}
          />
        </div>
      </div>

      {/* Right-click context menu */}
      {menu && (
        <div
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: 'fixed', left: menu.x, top: menu.y, zIndex: 1000,
            minWidth: 200, background: C.panel, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: 4, boxShadow: '0 8px 28px rgba(0,0,0,0.45)',
          }}
        >
          <MenuItem
            label={`Sum on-hand for ${menu.drug || '—'}`}
            disabled={!menu.drug}
            onClick={() => showSummary(menu.drug, menu.x, menu.y, `On-hand — ${menu.drug}`)}
          />
          <MenuItem
            label={`Locations for ${menu.drug || '—'}`}
            disabled={!menu.drug}
            onClick={() => showSummary(menu.drug, menu.x, menu.y, `Locations — ${menu.drug}`)}
          />
          <MenuItem
            label="Row metadata"
            onClick={() => { setPanel({ title: 'Row metadata', x: menu.x, y: menu.y, kind: 'meta', row: menu.row }); setMenu(null) }}
          />
          <div style={{ height: 1, background: C.border, margin: '4px 2px' }} />
          <MenuItem label="Delete row" danger disabled={rowId(menu.row) == null} onClick={() => onDeleteRow(menu.row)} />
        </div>
      )}

      {/* Summary / metadata popover */}
      {panel && (
        <div
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: 'fixed', left: Math.min(panel.x, window.innerWidth - 320), top: Math.min(panel.y, window.innerHeight - 260),
            zIndex: 1001, width: 300, background: C.panel, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: 12, boxShadow: '0 8px 28px rgba(0,0,0,0.45)',
          }}
        >
          <div className="disp" style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>{panel.title}</div>

          {panel.kind === 'summary' && panel.summary && (
            <div style={{ fontSize: 12, color: C.text }}>
              <SummaryRow label="Total on hand" value={String(panel.summary.total_on_hand)} />
              <SummaryRow label="Rows" value={String(panel.summary.rows)} />
              <SummaryRow label="Locations" value={String(panel.summary.locations)} />
              <SummaryRow
                label="Days of supply"
                value={panel.summary.days_of_supply == null ? '—' : String(panel.summary.days_of_supply)}
              />
              <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '10px 0 4px' }}>BY LOCATION</div>
              {panel.summary.by_location.map((b) => (
                <div key={b.location} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '3px 0', borderTop: `1px solid ${C.border}` }}>
                  <span style={{ color: C.muted }}>{b.location}</span>
                  <span className="mono">{b.on_hand} on hand · {b.avg_daily_use}/day</span>
                </div>
              ))}
            </div>
          )}

          {panel.kind === 'meta' && panel.row && (
            <div style={{ fontSize: 12 }}>
              <SummaryRow label="id" value={rowId(panel.row) == null ? '(unsaved)' : String(rowId(panel.row))} />
              {COLUMNS.map((c) => (
                <SummaryRow key={c.key} label={c.name} value={String(panel.row?.[c.key] ?? '')} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MenuItem({ label, onClick, danger, disabled }: { label: string; onClick: () => void; danger?: boolean; disabled?: boolean }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={{
        display: 'block', width: '100%', textAlign: 'left',
        background: 'transparent', border: 'none', borderRadius: 6,
        padding: '7px 10px', fontSize: 12.5,
        color: disabled ? C.muted2 : danger ? C.red : C.text,
        cursor: disabled ? 'default' : 'pointer',
      }}
      onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.background = C.panelAlt }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
    >
      {label}
    </button>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '3px 0' }}>
      <span style={{ color: C.muted }}>{label}</span>
      <span className="mono">{value}</span>
    </div>
  )
}
