/**
 * Spreadsheet interop helpers for the Excel-like grid:
 *   - importWorkbook: read an .xlsx / .csv file into row objects
 *   - exportRows:     write row objects back out to an .xlsx file
 *   - parseClipboard: turn pasted Excel/Sheets TSV into a 2D string matrix
 */
import * as XLSX from 'xlsx'

export interface GridColumn {
  key: string
  name: string
  editable?: boolean
  width?: number
}

export type Row = Record<string, string | number>

/** Read the first sheet of an .xlsx/.csv file into row objects keyed by column. */
export async function importWorkbook(file: File, columns: GridColumn[]): Promise<Row[]> {
  const buf = await file.arrayBuffer()
  const wb = XLSX.read(buf, { type: 'array' })
  const first = wb.SheetNames[0]
  if (!first) return []
  const sheet = wb.Sheets[first]
  // Read as an array-of-arrays so header naming mismatches don't drop columns.
  const matrix = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, blankrows: false })
  if (matrix.length === 0) return []

  const header = matrix[0].map((h) => String(h).trim().toLowerCase())
  const body = matrix.slice(1)

  // Map incoming header names to our column keys where they match; otherwise
  // fall back to positional mapping against the declared columns.
  const colIndex: (number | null)[] = columns.map((col) => {
    const byName = header.indexOf(col.name.toLowerCase())
    if (byName !== -1) return byName
    const byKey = header.indexOf(col.key.toLowerCase())
    return byKey !== -1 ? byKey : null
  })

  return body
    .filter((r) => r.some((c) => c !== '' && c != null))
    .map((r) => {
      const row: Row = {}
      columns.forEach((col, i) => {
        const src = colIndex[i]
        const raw = src != null ? r[src] : r[i]
        row[col.key] = raw == null ? '' : (raw as string | number)
      })
      return row
    })
}

/** Export row objects to an .xlsx download, using column display names as headers. */
export function exportRows(rows: Row[], columns: GridColumn[], filename: string): void {
  const header = columns.map((c) => c.name)
  const body = rows.map((r) => columns.map((c) => r[c.key] ?? ''))
  const sheet = XLSX.utils.aoa_to_sheet([header, ...body])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, sheet, 'Sheet1')
  XLSX.writeFile(wb, filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`)
}

/** Parse clipboard text (Excel/Sheets copy = tab-separated, newline rows). */
export function parseClipboard(text: string): string[][] {
  return text
    .replace(/\r/g, '')
    .replace(/\n$/, '') // trailing newline Excel appends
    .split('\n')
    .map((line) => line.split('\t'))
}
