/**
 * Reusable Excel-like data grid.
 *
 * Wraps react-data-grid to feel like a spreadsheet:
 *   - a frozen row-number gutter (1, 2, 3 …) and a frozen first data column
 *   - a cell-reference box (e.g. "B3") like Excel's name box
 *   - editable cells, gridlines, and the sheet padded with blank rows so it
 *     reads as an open worksheet rather than a short table
 *   - import from .xlsx / .csv (SheetJS) + export to .xlsx (blank rows dropped)
 *   - paste a block from Excel / Sheets (parses clipboard TSV, writes from the
 *     selected cell, growing rows as needed)
 *
 * Data is held by the parent (controlled): pass `rows` + `onRowsChange`.
 */
import { useCallback, useMemo, useRef, useState } from 'react'
import RDG, { textEditor } from 'react-data-grid'
import type { Column } from 'react-data-grid'
import 'react-data-grid/lib/styles.css'
import { Download, Upload, Plus, Trash2 } from 'lucide-react'
import { C } from '../../theme'
import { exportRows, importWorkbook, parseClipboard, type GridColumn, type Row } from './xlsx'

interface Props {
  columns: GridColumn[]
  rows: Row[]
  onRowsChange: (rows: Row[]) => void
  /** base filename for import/export, e.g. "stock" */
  name: string
  /** a fresh empty row (all declared keys present) */
  emptyRow: () => Row
  /** minimum blank rows to render so the sheet looks like a worksheet */
  minRows?: number
  /** optional per-row CSS class for data cells (e.g. mark forecast rows red) */
  rowClass?: (row: Row) => string | undefined
  /** stable id for a row (used by callers that persist per-row) */
  getRowId?: (row: Row) => number | string
  /**
   * Called for each row that changed via inline cell editing (in addition to
   * onRowsChange). Lets the parent persist a single edited row incrementally.
   */
  onCellEdited?: (row: Row) => void
  /**
   * Called on right-click over a data cell with the currently-selected data row
   * and the pointer position. The grid already calls preventDefault().
   */
  onContextMenu?: (row: Row, x: number, y: number) => void
  /** click a data column header (e.g. to configure that column as a feature) */
  onHeaderClick?: (colKey: string) => void
}

const ROWNUM_KEY = '__rn__'

/** Excel-style column letters: 0 -> A, 25 -> Z, 26 -> AA … */
function colLetter(n: number): string {
  let s = ''
  n += 1
  while (n > 0) {
    const r = (n - 1) % 26
    s = String.fromCharCode(65 + r) + s
    n = Math.floor((n - 1) / 26)
  }
  return s
}

const isBlank = (row: Row, columns: GridColumn[]) =>
  columns.every((c) => row[c.key] === '' || row[c.key] == null)

export default function DataGrid({
  columns,
  rows,
  onRowsChange,
  name,
  emptyRow,
  minRows = 50,
  rowClass,
  getRowId,
  onCellEdited,
  onContextMenu,
  onHeaderClick,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const selected = useRef<{ rowIdx: number; colKey: string }>({ rowIdx: 0, colKey: columns[0]?.key })
  const [cellRef, setCellRef] = useState('A1')
  const [hint, setHint] = useState('Paste a block from Excel, or Import a file')

  // Pad with blank rows so the worksheet fills the screen.
  const displayRows = useMemo<Row[]>(() => {
    if (rows.length >= minRows) return rows
    const pad = Array.from({ length: minRows - rows.length }, emptyRow)
    return [...rows, ...pad]
  }, [rows, minRows, emptyRow])

  // Stable React keys per row. Real rows use the caller's id; the blank padding
  // rows (which have no id) fall back to their position so keys never collide.
  const keyMap = useMemo(() => {
    const m = new WeakMap<Row, number | string>()
    displayRows.forEach((r, i) => {
      let k: number | string = i
      if (getRowId) {
        const id = getRowId(r)
        if (id != null && id !== '' && !(typeof id === 'number' && Number.isNaN(id))) k = id
        else k = `__pad_${i}`
      }
      m.set(r, k)
    })
    return m
  }, [displayRows, getRowId])
  const rowKeyGetter = useCallback((r: Row) => keyMap.get(r) ?? 0, [keyMap])

  const rdgColumns: Column<Row>[] = useMemo(() => {
    const gutter: Column<Row> = {
      key: ROWNUM_KEY,
      name: '',
      frozen: true,
      width: 52,
      resizable: false,
      editable: false,
      cellClass: 'rdg-rownum',
      headerCellClass: 'rdg-rownum-header',
      renderCell: ({ rowIdx }) => rowIdx + 1,
    }
    const data: Column<Row>[] = columns.map((col, i) => ({
      key: col.key,
      name: col.name,
      editable: col.editable ?? true,
      resizable: true,
      frozen: i === 0, // freeze the first data column, Excel-style
      width: col.width,
      minWidth: 70,
      renderEditCell: textEditor,
      cellClass: rowClass ? (row: Row) => rowClass(row) : undefined,
      // Clickable header ("column tab") so callers can configure a column.
      renderHeaderCell: onHeaderClick
        ? ({ column }) => (
            <div
              onClick={() => onHeaderClick(column.key)}
              style={{ cursor: 'pointer', width: '100%', height: '100%', display: 'flex', alignItems: 'center', gap: 4 }}
              title="Configure column"
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{column.name}</span>
              <span style={{ opacity: 0.55, fontSize: 9 }}>▾</span>
            </div>
          )
        : undefined,
    }))
    return [gutter, ...data]
  }, [columns, rowClass, onHeaderClick])

  const handleImport = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      try {
        const imported = await importWorkbook(file, columns)
        onRowsChange(imported)
        setHint(`Imported ${imported.length} rows from ${file.name}`)
      } catch (err) {
        setHint(`Import failed: ${err instanceof Error ? err.message : 'unknown error'}`)
      } finally {
        if (fileRef.current) fileRef.current.value = ''
      }
    },
    [columns, onRowsChange],
  )

  // Block paste from Excel/Sheets: write the TSV matrix from the selected cell.
  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const text = e.clipboardData.getData('text/plain')
      if (!text) return
      e.preventDefault()
      const matrix = parseClipboard(text)
      if (matrix.length === 0) return

      const startRow = selected.current.rowIdx ?? 0
      const startCol = Math.max(0, columns.findIndex((c) => c.key === selected.current.colKey))
      const next = [...displayRows]

      matrix.forEach((line, r) => {
        const targetIdx = startRow + r
        while (next.length <= targetIdx) next.push(emptyRow())
        const row = { ...next[targetIdx] }
        line.forEach((val, c) => {
          const col = columns[startCol + c]
          if (col && (col.editable ?? true)) row[col.key] = val
        })
        next[targetIdx] = row
      })

      onRowsChange(next)
      setHint(`Pasted ${matrix.length} × ${matrix[0].length} block at ${cellRef}`)
    },
    [columns, displayRows, onRowsChange, emptyRow, cellRef],
  )

  // Inline edits: forward the full set (existing behavior) and, if the parent
  // wants per-row persistence, hand it each row that actually changed.
  const handleRowsChange = useCallback(
    (newRows: Row[], data?: { indexes: number[] }) => {
      onRowsChange(newRows)
      if (onCellEdited && data?.indexes) {
        for (const idx of data.indexes) {
          const row = newRows[idx]
          if (row) onCellEdited(row)
        }
      }
    },
    [onRowsChange, onCellEdited],
  )

  // Right-click over a data cell -> parent-supplied context menu. Ignore the
  // frozen row-number gutter and clicks outside any data row.
  const handleContextMenu = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!onContextMenu) return
      const target = e.target as HTMLElement
      if (target.closest('.rdg-rownum') || target.closest('.rdg-rownum-header')) return
      const row = displayRows[selected.current.rowIdx]
      if (!row) return
      e.preventDefault()
      onContextMenu(row, e.clientX, e.clientY)
    },
    [onContextMenu, displayRows],
  )

  const btn: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    background: C.panelAlt,
    color: C.text,
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    padding: '6px 10px',
    fontSize: 12,
    cursor: 'pointer',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%', minHeight: 0 }}>
      {/* Formula-bar-style toolbar */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span
          className="mono"
          style={{
            minWidth: 56,
            textAlign: 'center',
            background: C.bg,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: '6px 8px',
            fontSize: 12,
            color: C.teal,
            fontWeight: 600,
          }}
        >
          {cellRef}
        </span>
        <div style={{ width: 1, height: 22, background: C.border }} />
        <button style={btn} onClick={() => fileRef.current?.click()}>
          <Upload size={13} /> Import
        </button>
        <button style={btn} onClick={() => exportRows(displayRows.filter((r) => !isBlank(r, columns)), columns, name)}>
          <Download size={13} /> Export
        </button>
        <button style={btn} onClick={() => onRowsChange([...displayRows, emptyRow()])}>
          <Plus size={13} /> Add row
        </button>
        <button style={{ ...btn, color: C.red }} onClick={() => onRowsChange([])}>
          <Trash2 size={13} /> Clear
        </button>
        <span className="mono" style={{ fontSize: 10.5, color: C.muted2, marginLeft: 4 }}>
          {hint}
        </span>
        <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" style={{ display: 'none' }} onChange={handleImport} />
      </div>

      {/* Sheet */}
      <div style={{ flex: 1, minHeight: 0 }} onPaste={handlePaste} onContextMenu={handleContextMenu}>
        <RDG
          columns={rdgColumns}
          rows={displayRows}
          rowKeyGetter={getRowId ? rowKeyGetter : undefined}
          onRowsChange={handleRowsChange}
          onSelectedCellChange={(args) => {
            if (args.rowIdx >= 0 && args.column && args.column.key !== ROWNUM_KEY) {
              selected.current = { rowIdx: args.rowIdx, colKey: args.column.key }
              const dataColIdx = columns.findIndex((c) => c.key === args.column.key)
              setCellRef(`${colLetter(Math.max(0, dataColIdx))}${args.rowIdx + 1}`)
            }
          }}
          className="rdg rdg-excel"
          style={{ height: '100%' }}
        />
      </div>
    </div>
  )
}
