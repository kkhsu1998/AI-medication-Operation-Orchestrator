/**
 * Forecast tab — daily demand with an editable feature grid.
 *
 * Left rail selects the series (All medications = aggregate history, or a single
 * drug). The right pane is the Excel grid whose COLUMNS ARE THE FEATURES: click a
 * column header (▾) to configure it — categorical encoder, lag range N-1…N-n,
 * calendar kind, or a derived formula — toggle include/exclude, or add columns.
 * Predict trains a multivariate model (XGBoost / Random Forest) on the included
 * columns for the selected drug and draws history (white) + forecast (red).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { TrendingUp, RotateCcw, Plus, X } from 'lucide-react'
import DataGrid from '../components/DataGrid/DataGrid'
import type { GridColumn, Row } from '../components/DataGrid/xlsx'
import {
  getItem, getOverview, getFeatureOptions, getSample, predictSeries, trainForecast,
  type ForecastOverview, type ModelType, type FeatureOptions, type FeatureSpec, type TrainResult,
  type SampleData,
} from '../api/forecast'
import { C } from '../theme'

const MON_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const label = (iso: string) => {
  const [, m, d] = iso.split('-')
  return `${MON_ABBR[Number(m) - 1]} ${Number(d)}`
}
const AGG = 'ALL'
const MODEL_LABEL: Record<string, string> = {
  xgboost: 'XGBoost',
  random_forest: 'Random Forest',
  arima: 'ARIMA',
  moving_average: 'Moving Avg',
}
// ARIMA / Moving Avg are univariate: they forecast the series directly and
// ignore the feature grid (which only tree models consume).
const UNIVARIATE: ModelType[] = ['arima', 'moving_average']

interface Point { date: string; value: number }

// ---- Feature grid: each column IS a data field / feature ----
type ColRole = 'time' | 'target' | 'categorical' | 'lag' | 'calendar' | 'derived'
interface FeatureCol {
  key: string
  name: string
  role: ColRole
  include: boolean
  encoder?: string
  nDims?: number      // embedding dimensionality
  lagN?: number
  kind?: string
  formula?: string
}

const SAMPLE_KINDS = ['dow', 'month', 'day']

const seedColumns = (): FeatureCol[] => [
  { key: 'date', name: 'Date', role: 'time', include: true },
  { key: 'location', name: 'Location', role: 'categorical', include: true, encoder: 'onehot' },
  { key: 'quantity', name: 'Quantity', role: 'target', include: true },
  { key: 'lag_range', name: 'Lag N-1 … N-7', role: 'lag', include: true, lagN: 7 },
  { key: 'cal_dow', name: 'Calendar · dow', role: 'calendar', include: true, kind: 'dow' },
]

const calValue = (iso: string, kind: string): number => {
  const dt = new Date(iso + 'T00:00:00Z')
  if (kind === 'month') return dt.getUTCMonth() + 1
  if (kind === 'day') return dt.getUTCDate()
  return dt.getUTCDay()
}

const evalFormula = (formula: string, scope: Record<string, number>): number | undefined => {
  if (!formula.trim()) return undefined
  try {
    const keys = Object.keys(scope)
    // eslint-disable-next-line @typescript-eslint/no-implied-eval
    const fn = new Function(...keys, `"use strict"; return (${formula});`)
    const v = fn(...keys.map((k) => scope[k]))
    return typeof v === 'number' && Number.isFinite(v) ? v : undefined
  } catch {
    return undefined
  }
}

const round2 = (v: number) => Math.round(v * 100) / 100

export default function Forecast() {
  const [overview, setOverview] = useState<ForecastOverview | null>(null)
  const [selected, setSelected] = useState<string>(AGG)
  const [base, setBase] = useState<Point[]>([])          // history for the chart
  const [model, setModel] = useState<ModelType>('xgboost')
  const [steps, setSteps] = useState(14)
  const [normalization, setNormalization] = useState('standard')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartFrac, setChartFrac] = useState(0.55)

  const [options, setOptions] = useState<FeatureOptions | null>(null)
  const [trained, setTrained] = useState<TrainResult | null>(null)
  const [sample, setSample] = useState<SampleData['rows']>([])
  const [featureCols, setFeatureCols] = useState<FeatureCol[]>(seedColumns)
  const [activeCol, setActiveCol] = useState<string | null>(null)
  const colSeq = useRef(0)
  const splitRef = useRef<HTMLDivElement>(null)

  const isAll = selected === AGG

  const startDrag = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const onMove = (ev: MouseEvent) => {
      const el = splitRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      setChartFrac(Math.max(0.2, Math.min(0.8, (ev.clientX - rect.left) / rect.width)))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [])

  useEffect(() => {
    getOverview()
      .then((o) => { setOverview(o); setError(null) })
      .catch(() => setError('Backend not reachable — start it with: uvicorn app.main:app'))
    getFeatureOptions()
      .then((o) => { setOptions(o); if (o.normalizers.length && !o.normalizers.includes(normalization)) setNormalization(o.normalizers[0]) })
      .catch(() => { /* optional */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // History for the chart (aggregate or single drug).
  useEffect(() => {
    setTrained(null)
    if (!overview) return
    if (isAll) { setBase(overview.days.map((d, i) => ({ date: d, value: overview.aggregate[i] }))); return }
    getItem(selected)
      .then((it) => { setBase(it.days.map((d, i) => ({ date: d, value: it.values[i] }))); setError(null) })
      .catch(() => setError(`Could not load history for ${selected}`))
  }, [selected, isAll, overview])

  // Base panel rows for the feature grid (one drug).
  useEffect(() => {
    if (isAll || !selected) return
    getSample(selected)
      .then((s) => { setSample(s.rows); setError(null) })
      .catch(() => setError(`Could not load sample rows for ${selected}`))
  }, [selected, isAll])

  const grouped = useMemo(() => {
    const g: Record<string, string[]> = {}
    ;(overview?.medications ?? []).forEach((d) => { (g[d[0].toUpperCase()] ||= []).push(d) })
    return g
  }, [overview])

  const allModels: ModelType[] = ['xgboost', 'random_forest', 'arima', 'moving_average']
  const isUnivariate = UNIVARIATE.includes(model)

  const runPredict = () => {
    if (isAll) return
    setBusy(true)
    setError(null)

    if (isUnivariate) {
      // ARIMA / Moving Avg: forecast the drug's daily series directly. The lag
      // column's n doubles as the AR order / averaging window.
      const series = base.map((p) => p.value)
      const lagCol = featureCols.find((c) => c.role === 'lag' && c.include)
      predictSeries(series, steps, model, lagCol?.lagN)
        .then((preds) => {
          let d = base[base.length - 1]?.date ?? new Date().toISOString().slice(0, 10)
          const predictions = preds.map((v) => {
            const dt = new Date(d + 'T00:00:00Z')
            dt.setUTCDate(dt.getUTCDate() + 1)
            d = dt.toISOString().slice(0, 10)
            return { date: d, value: v }
          })
          setTrained({
            model, normalization: 'none', steps, n_train_rows: series.length,
            features_used: [], history: [], predictions,
          })
          setError(null)
        })
        .catch((e) => { setTrained(null); setError(`Predict failed: ${e instanceof Error ? e.message : String(e)}`) })
        .finally(() => setBusy(false))
      return
    }

    const specs: FeatureSpec[] = []
    for (const c of featureCols) {
      if (!c.include) continue
      switch (c.role) {
        case 'lag': for (let k = 1; k <= Math.max(1, c.lagN ?? 1); k++) specs.push({ type: 'lag', lag: k }); break
        case 'calendar': specs.push({ type: 'calendar', kind: c.kind ?? 'dow' }); break
        case 'categorical':
          specs.push({
            type: 'categorical', column: 'location', encoder: c.encoder ?? 'onehot',
            n_dims: c.encoder === 'embedding' ? Math.max(1, Math.min(32, c.nDims ?? 4)) : undefined,
          })
          break
        case 'derived': if (c.formula?.trim()) specs.push({ type: 'derived', name: c.name, formula: c.formula.trim() }); break
        default: break
      }
    }
    trainForecast(selected, steps, model, normalization, specs)
      .then((res) => { setTrained(res); setError(null) })
      .catch((e) => { setTrained(null); setError(`Predict failed: ${e instanceof Error ? e.message : String(e)}`) })
      .finally(() => setBusy(false))
  }

  // ---- Feature-column editing ----
  const patchCol = (key: string, patch: Partial<FeatureCol>) => setFeatureCols((prev) => prev.map((c) => (c.key === key ? { ...c, ...patch } : c)))
  const removeCol = (key: string) => setFeatureCols((prev) => prev.filter((c) => c.key !== key))
  const nextKey = (prefix: string) => `${prefix}_${(colSeq.current += 1)}`
  const addLagCol = () => { const key = nextKey('lag'); setFeatureCols((p) => [...p, { key, name: 'Lag N-1 … N-7', role: 'lag', include: true, lagN: 7 }]); setActiveCol(key) }
  const addCalendarCol = (kind: string) => { const key = nextKey('cal'); setFeatureCols((p) => [...p, { key, name: `Calendar · ${kind}`, role: 'calendar', include: true, kind }]); setActiveCol(key) }
  const addDerivedCol = () => { const key = nextKey('d'); setFeatureCols((p) => [...p, { key, name: 'derived', role: 'derived', include: true, formula: '' }]); setActiveCol(key) }

  // ---- Grid preview (client-side feature computation) ----
  const sortedSample = useMemo(() =>
    [...sample].sort((a, b) => (a.location < b.location ? -1 : a.location > b.location ? 1 : (a.date < b.date ? -1 : 1))),
    [sample])

  const latticeColumns: GridColumn[] = useMemo(
    () => featureCols.map((c) => ({
      key: c.key,
      name: (c.include ? '' : '· ') + c.name,
      width: c.role === 'time' ? 118 : c.role === 'derived' ? 150 : 120,
      editable: false,
    })),
    [featureCols],
  )

  const latticeRows: Row[] = useMemo(() => {
    const N = Math.min(60, sortedSample.length)
    const maxLag = Math.max(1, ...featureCols.filter((c) => c.role === 'lag').map((c) => c.lagN ?? 1))
    const hist: Record<string, number[]> = {}
    const out: Row[] = []
    for (let i = 0; i < sortedSample.length; i++) {
      const r = sortedSample[i]
      const prior = (hist[r.location] ||= [])
      if (i < N) {
        const scope: Record<string, number> = { quantity: r.quantity }
        for (let k = 1; k <= maxLag; k++) { const v = prior[prior.length - k]; if (v !== undefined) scope[`lag_${k}`] = v }
        for (const c of featureCols) if (c.role === 'calendar') scope[`cal_${c.kind ?? 'dow'}`] = calValue(r.date, c.kind ?? 'dow')
        const gridRow: Row = {}
        for (const c of featureCols) {
          switch (c.role) {
            case 'time': gridRow[c.key] = r.date; break
            case 'target': gridRow[c.key] = r.quantity; break
            case 'categorical': gridRow[c.key] = r.location; break
            case 'lag': { const v = prior[prior.length - 1]; gridRow[c.key] = v === undefined ? '' : v; break }
            case 'calendar': gridRow[c.key] = calValue(r.date, c.kind ?? 'dow'); break
            case 'derived': { const v = evalFormula(c.formula ?? '', scope); if (v !== undefined) { scope[c.key] = v; gridRow[c.key] = round2(v) } else gridRow[c.key] = ''; break }
          }
        }
        out.push(gridRow)
      }
      prior.push(r.quantity)
    }
    return out
  }, [sortedSample, featureCols])

  const emptyLatticeRow = useCallback((): Row => Object.fromEntries(featureCols.map((c) => [c.key, ''])), [featureCols])

  const activeColumn = featureCols.find((c) => c.key === activeCol) ?? null
  const locEncoders = options?.categoricals?.find((c) => c.column === 'location')?.encoders ?? ['onehot', 'ordinal']
  const calendarKinds = options?.calendar ?? SAMPLE_KINDS

  // ---- Chart data ----
  // Always show the FULL history (base); when trained, append the forecast to
  // the end (the last history point also seeds Forecast so the red line joins).
  const chartData = useMemo(() => {
    const hist = base.map((p, i) => ({
      date: label(p.date),
      Actual: p.value,
      Forecast: (trained && i === base.length - 1) ? p.value : (null as number | null),
    }))
    if (!trained) return hist
    return [...hist, ...trained.predictions.map((p) => ({ date: label(p.date), Actual: null as number | null, Forecast: p.value }))]
  }, [base, trained])

  const railItem = (name: string, active: boolean, onClick: () => void, sub?: string) => (
    <button key={name} onClick={onClick} style={{
      display: 'block', width: '100%', textAlign: 'left',
      background: active ? C.panelAlt : 'transparent', border: `1px solid ${active ? C.teal : 'transparent'}`,
      borderRadius: 7, padding: '8px 10px', color: active ? C.text : C.muted, fontSize: 12.5, fontWeight: active ? 600 : 400, cursor: 'pointer',
    }}>
      {name}{sub && <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>{sub}</div>}
    </button>
  )

  const selStyle: React.CSSProperties = { background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', fontSize: 12 }
  const smallBtn = (extra?: React.CSSProperties): React.CSSProperties => ({
    display: 'inline-flex', alignItems: 'center', gap: 4, background: C.panelAlt, color: C.text,
    border: `1px solid ${C.border}`, borderRadius: 6, padding: '5px 9px', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', ...extra,
  })

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
      <aside style={{ width: 232, flexShrink: 0, borderRight: `1px solid ${C.border}`, background: C.panel, overflowY: 'auto', padding: 12 }}>
        <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '2px 0 8px' }}>VIEW</div>
        {railItem('All medications', isAll, () => setSelected(AGG), 'aggregate · daily')}
        <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '14px 0 6px' }}>
          MEDICATIONS{overview ? ` (${overview.medications.length})` : ''}
        </div>
        {Object.keys(grouped).sort().map((letter) => (
          <div key={letter} style={{ marginBottom: 6 }}>
            <div className="disp" style={{ fontSize: 11, color: C.muted2, padding: '2px 10px' }}>{letter}</div>
            {grouped[letter].map((drug) => railItem(drug, selected === drug, () => setSelected(drug)))}
          </div>
        ))}
      </aside>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 16px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
          <div className="disp" style={{ fontSize: 17, fontWeight: 700 }}>Forecast — {isAll ? 'All medications' : selected}</div>
          <div style={{ fontSize: 12, color: C.muted }}>Configure feature columns (click a header ▾) and Predict — history white, forecast red.</div>
        </div>

        {/* Controls row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '8px 10px' }}>
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>MODEL</span>
          {allModels.map((m) => (
            <button key={m} onClick={() => setModel(m)} style={{
              background: model === m ? C.teal : C.panelAlt, color: model === m ? '#0F141B' : C.text,
              border: `1px solid ${model === m ? C.teal : C.border}`, borderRadius: 6, padding: '6px 11px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>{MODEL_LABEL[m] ?? m}</button>
          ))}
          <div style={{ width: 1, height: 22, background: C.border, margin: '0 4px' }} />
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>NORM</span>
          <select value={normalization} onChange={(e) => setNormalization(e.target.value)} disabled={isUnivariate}
            title={isUnivariate ? 'Not used by ARIMA / Moving Avg' : undefined}
            style={{ ...selStyle, opacity: isUnivariate ? 0.5 : 1 }}>
            {(options?.normalizers ?? ['none', 'standard', 'minmax']).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>DAYS</span>
          <input type="number" min={1} max={365} value={steps} onChange={(e) => setSteps(Math.max(1, Math.min(365, Number(e.target.value) || 1)))}
            style={{ width: 64, background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', fontSize: 12 }} />
          <button onClick={runPredict} disabled={busy || isAll} title={isAll ? 'Pick a single medication to forecast' : undefined} style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, background: C.teal, color: '#0F141B', border: 'none',
            borderRadius: 6, padding: '7px 14px', fontSize: 12.5, fontWeight: 700, cursor: busy ? 'wait' : (isAll ? 'not-allowed' : 'pointer'), opacity: isAll ? 0.5 : 1,
          }}><TrendingUp size={14} /> {busy ? 'Predicting…' : `Predict ${steps} days`}</button>
          {isAll && <span style={{ fontSize: 11, color: C.amber }}>Pick a single medication to forecast</span>}
          {trained && (
            <>
              <button onClick={() => setTrained(null)} style={{ ...smallBtn(), color: C.muted }}><RotateCcw size={13} /> Reset</button>
              <div style={{ width: 1, height: 22, background: C.border, margin: '0 4px' }} />
              <span className="mono" style={{ fontSize: 10.5, color: C.muted }}>{trained.n_train_rows} train rows</span>
            </>
          )}
        </div>

        {trained && trained.features_used.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>FEATURES USED</span>
            {trained.features_used.map((f) => (
              <span key={f} className="mono" style={{ fontSize: 10.5, color: C.teal, background: C.teal + '18', border: `1px solid ${C.teal}55`, borderRadius: 5, padding: '2px 7px' }}>{f}</span>
            ))}
          </div>
        )}

        {error && <div style={{ background: C.red + '22', border: `1px solid ${C.red}`, color: C.red, padding: '9px 12px', borderRadius: 8, fontSize: 12 }}>{error}</div>}

        <div ref={splitRef} style={{ flex: 1, minHeight: 280, display: 'flex', alignItems: 'stretch' }}>
          {/* Chart pane (LEFT) */}
          <div style={{ flexBasis: `${chartFrac * 100}%`, flexGrow: 0, flexShrink: 0, minWidth: 0, display: 'flex', flexDirection: 'column', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '12px 16px 8px' }}>
            <div className="mono" style={{ fontSize: 10.5, color: C.muted2, marginBottom: 10 }}>DAILY DEMAND — ACTUAL vs FORECAST ({MODEL_LABEL[model] ?? model})</div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 6, right: 24, bottom: 6, left: 0 }}>
                  <CartesianGrid stroke={C.border} strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke={C.muted} fontSize={11} minTickGap={48} />
                  <YAxis stroke={C.muted} fontSize={11} width={54} />
                  <Tooltip contentStyle={{ background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="Actual" stroke="#FFFFFF" strokeWidth={1.8} dot={false} connectNulls isAnimationActive={false} />
                  <Line type="monotone" dataKey="Forecast" stroke={C.red} strokeWidth={2.2} strokeDasharray="6 3" dot={false} connectNulls isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Draggable divider */}
          <div onMouseDown={startDrag} role="separator" aria-orientation="vertical" style={{ flex: '0 0 10px', cursor: 'col-resize', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 3, height: '100%', borderRadius: 3, background: C.border }} />
          </div>

          {/* RIGHT pane — the feature grid (columns = features) */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            {isAll ? (
              <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, color: C.muted2, fontSize: 12.5, textAlign: 'center', padding: 24 }}>
                Pick a single medication in the left rail to open its feature grid.
              </div>
            ) : (
              <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {/* Column adders */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '7px 10px' }}>
                  <span className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>
                    {isUnivariate
                      ? `COLUMNS = FEATURES · ${MODEL_LABEL[model]} is univariate — only the lag n is used`
                      : 'COLUMNS = FEATURES · click a header (▾) to configure'}
                  </span>
                  <div style={{ flex: 1 }} />
                  <span className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>+ ADD</span>
                  <button onClick={addLagCol} style={smallBtn()}><Plus size={12} /> lag</button>
                  <button onClick={() => addCalendarCol(calendarKinds[0] ?? 'dow')} style={smallBtn()}><Plus size={12} /> calendar</button>
                  <button onClick={addDerivedCol} style={smallBtn()}><Plus size={12} /> derived</button>
                </div>

                {/* Config strip for the active column */}
                {activeColumn && (
                  <div style={{ background: C.panelAlt, border: `1px solid ${C.teal}66`, borderRadius: 8, padding: '9px 11px', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span className="mono" style={{ fontSize: 9.5, color: C.teal }}>{activeColumn.role.toUpperCase()} · {activeColumn.name}</span>
                    <div style={{ width: 1, height: 20, background: C.border }} />
                    {activeColumn.role === 'target' && <span style={{ fontSize: 12, color: C.muted }}>Target — the value being predicted.</span>}
                    {activeColumn.role === 'time' && (
                      <>
                        <span style={{ fontSize: 12, color: C.muted }}>Time — add a calendar feature:</span>
                        {calendarKinds.map((k) => <button key={k} onClick={() => addCalendarCol(k)} style={smallBtn()}><Plus size={12} /> cal_{k}</button>)}
                      </>
                    )}
                    {activeColumn.role === 'categorical' && (
                      <>
                        <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>ENCODER</span>
                        <select value={activeColumn.encoder ?? 'onehot'} onChange={(e) => patchCol(activeColumn.key, { encoder: e.target.value })} style={selStyle}>
                          {locEncoders.map((enc) => <option key={enc} value={enc}>{enc}</option>)}
                        </select>
                        {activeColumn.encoder === 'embedding' && (
                          <>
                            <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>N_DIMS</span>
                            <input type="number" min={1} max={32} value={activeColumn.nDims ?? 4}
                              onChange={(e) => patchCol(activeColumn.key, { nDims: Math.max(1, Math.min(32, Number(e.target.value) || 1)) })}
                              style={{ ...selStyle, width: 58 }} />
                            <span className="mono" style={{ fontSize: 10.5, color: C.muted2 }}>→ loc_emb_0 … loc_emb_{(activeColumn.nDims ?? 4) - 1}</span>
                          </>
                        )}
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: C.text }}>
                          <input type="checkbox" checked={activeColumn.include} onChange={(e) => patchCol(activeColumn.key, { include: e.target.checked })} /> Include
                        </label>
                      </>
                    )}
                    {activeColumn.role === 'lag' && (
                      <>
                        <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>N-1 … N-</span>
                        <input type="number" min={1} max={90} value={activeColumn.lagN ?? 7}
                          onChange={(e) => { const n = Math.max(1, Math.min(90, Number(e.target.value) || 1)); patchCol(activeColumn.key, { lagN: n, name: `Lag N-1 … N-${n}` }) }}
                          style={{ ...selStyle, width: 60 }} />
                        <span className="mono" style={{ fontSize: 10.5, color: C.muted2 }}>→ lag_1 … lag_{activeColumn.lagN ?? 7}</span>
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: C.text }}>
                          <input type="checkbox" checked={activeColumn.include} onChange={(e) => patchCol(activeColumn.key, { include: e.target.checked })} /> Include
                        </label>
                      </>
                    )}
                    {activeColumn.role === 'calendar' && (
                      <>
                        <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>KIND</span>
                        <select value={activeColumn.kind ?? 'dow'} onChange={(e) => patchCol(activeColumn.key, { kind: e.target.value, name: `Calendar · ${e.target.value}` })} style={selStyle}>
                          {calendarKinds.map((k) => <option key={k} value={k}>{k}</option>)}
                        </select>
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: C.text }}>
                          <input type="checkbox" checked={activeColumn.include} onChange={(e) => patchCol(activeColumn.key, { include: e.target.checked })} /> Include
                        </label>
                        <button onClick={() => { removeCol(activeColumn.key); setActiveCol(null) }} style={smallBtn({ color: C.red })}><X size={12} /> Remove</button>
                      </>
                    )}
                    {activeColumn.role === 'derived' && (
                      <>
                        <input placeholder="name" value={activeColumn.name} onChange={(e) => patchCol(activeColumn.key, { name: e.target.value })} style={{ ...selStyle, width: 110 }} />
                        <input placeholder="lag_1 * 0.5 + lag_7" value={activeColumn.formula ?? ''} onChange={(e) => patchCol(activeColumn.key, { formula: e.target.value })} style={{ ...selStyle, minWidth: 170, flex: 1 }} />
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: C.text }}>
                          <input type="checkbox" checked={activeColumn.include} onChange={(e) => patchCol(activeColumn.key, { include: e.target.checked })} /> Include
                        </label>
                        <button onClick={() => { removeCol(activeColumn.key); setActiveCol(null) }} style={smallBtn({ color: C.red })}><X size={12} /> Remove</button>
                      </>
                    )}
                    <div style={{ flex: 1 }} />
                    <button onClick={() => setActiveCol(null)} title="Close" style={{ background: 'transparent', border: 'none', color: C.muted, cursor: 'pointer', display: 'inline-flex', padding: 2 }}><X size={14} /></button>
                  </div>
                )}

                {/* The Excel grid IS the feature editor */}
                <div style={{ flex: 1, minHeight: 0 }}>
                  <DataGrid
                    key={selected}
                    columns={latticeColumns}
                    rows={latticeRows}
                    onRowsChange={() => {}}
                    name={`features-${selected.split(' ')[0].toLowerCase()}`}
                    emptyRow={emptyLatticeRow}
                    minRows={Math.max(latticeRows.length, 12)}
                    onHeaderClick={(colKey) => setActiveCol((k) => (k === colKey ? null : colKey))}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
