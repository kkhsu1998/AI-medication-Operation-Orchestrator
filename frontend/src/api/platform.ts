/**
 * API client for the platform panels: Dashboard, Orchestrator, Audit, Settings.
 */
const BASE = import.meta.env.VITE_API_URL || ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path} -> ${res.status}`)
  return res.json()
}

// ---- Dashboard ----
export interface Issue {
  id: string
  kind: 'stockout' | 'shortage' | 'expiration_risk' | 'overstock'
  severity: number
  drug: string
  location: string
  on_hand: number
  days_of_supply: number | null
  detail: string
  options: { type: string; label: string; feasible: boolean; detail: string; score: number }[]
}
export interface Dashboard {
  inventory_rows: number
  medications: number
  locations: number
  total_units_on_hand: number
  issues_total: number
  issues_by_kind: Record<string, number>
  top_issues: Issue[]
  consumption_trend: { day: string; value: number }[]
}
export const getDashboard = () => get<Dashboard>('/api/v1/dashboard')

// ---- Orchestrator ----
export const getIssues = () => get<{ total: number; items: Issue[] }>('/api/v1/orchestrator/issues')

export interface DecisionPayload {
  issue_id: string
  drug: string
  location: string
  option_type: string
  decision: 'approved' | 'rejected'
  reason?: string
  approver_role: string
}
export async function postDecision(p: DecisionPayload): Promise<{ status: string; task_id: string | null }> {
  const res = await fetch(`${BASE}/api/v1/orchestrator/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p),
  })
  if (!res.ok) throw new Error(`decision -> ${res.status}`)
  return res.json()
}

// ---- Audit ----
export interface AuditEntry {
  id: number
  change_id: string
  ts: string
  actor: string
  action: string
  entity: string
  detail: string
}
export const getAudit = (limit = 100) => get<{ total: number; items: AuditEntry[] }>(`/api/v1/audit?limit=${limit}`)

// ---- Settings ----
export interface SettingItem {
  key: string
  value: number
  label: string
  group: string
}
export const getSettings = () => get<{ items: SettingItem[] }>('/api/v1/settings')
export async function patchSettings(values: Record<string, number>): Promise<{ items: SettingItem[] }> {
  const res = await fetch(`${BASE}/api/v1/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  })
  if (!res.ok) throw new Error(`settings -> ${res.status}`)
  return res.json()
}
