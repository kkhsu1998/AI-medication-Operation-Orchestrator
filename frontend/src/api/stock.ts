/**
 * Stock API — relational, paginated, incremental (per-row) saves.
 */
import type { Row } from '../components/DataGrid/xlsx'

const BASE = import.meta.env.VITE_API_URL || ''

export interface StockPage {
  items: Row[]
  total: number
  limit: number
  offset: number
}

export async function listStock(opts: { limit?: number; offset?: number; drug?: string } = {}): Promise<StockPage> {
  const p = new URLSearchParams()
  p.set('limit', String(opts.limit ?? 200))
  p.set('offset', String(opts.offset ?? 0))
  if (opts.drug) p.set('drug', opts.drug)
  const res = await fetch(`${BASE}/api/v1/stock?${p}`)
  if (!res.ok) throw new Error(`GET /stock -> ${res.status}`)
  return res.json()
}

export async function addRow(row: Row): Promise<Row> {
  const res = await fetch(`${BASE}/api/v1/stock`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(row),
  })
  if (!res.ok) throw new Error(`POST /stock -> ${res.status}`)
  return res.json()
}

export async function patchRow(id: number, fields: Row): Promise<Row> {
  const res = await fetch(`${BASE}/api/v1/stock/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fields),
  })
  if (!res.ok) throw new Error(`PATCH /stock/${id} -> ${res.status}`)
  return res.json()
}

export async function deleteRow(id: number): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/stock/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE /stock/${id} -> ${res.status}`)
}

export async function bulkReplace(rows: Row[]): Promise<{ total: number }> {
  const res = await fetch(`${BASE}/api/v1/stock`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items: rows }),
  })
  if (!res.ok) throw new Error(`PUT /stock -> ${res.status}`)
  return res.json()
}

export interface DrugSummary {
  drug: string
  total_on_hand: number
  rows: number
  locations: number
  days_of_supply: number | null
  by_location: { location: string; on_hand: number; avg_daily_use: number; rows: number }[]
}
export async function getSummary(drug: string): Promise<DrugSummary> {
  const res = await fetch(`${BASE}/api/v1/stock/summary?drug=${encodeURIComponent(drug)}`)
  if (!res.ok) throw new Error(`summary -> ${res.status}`)
  return res.json()
}
