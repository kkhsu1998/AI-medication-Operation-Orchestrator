/**
 * Orchestrator — detected operational issues with ranked recommendations and
 * one-click human approval. Mirrors the operating flow: detect → rank options
 * (transfer preferred over procurement) → approve/reject → task + audit.
 *
 * The system only recommends; a human must approve before any task is created.
 */
import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, XCircle, Star, ArrowRightLeft, ShoppingCart } from 'lucide-react'
import { getIssues, postDecision, type Issue } from '../api/platform'
import { kindOf } from '../kinds'
import { C } from '../theme'

const ROLES = ['Pharmacist', 'Manager', 'Clinician']
const REJECT_REASONS = ['Insufficient lead-time margin', 'Cost exceeds budget', 'Prefer alternate supplier', 'Clinical override', 'Other']
const KINDS = ['stockout', 'shortage', 'expiration_risk', 'overstock']

export default function Orchestrator() {
  const [issues, setIssues] = useState<Issue[]>([])
  const [total, setTotal] = useState(0)
  const [filter, setFilter] = useState<string>('all')
  const [role, setRole] = useState('Pharmacist')
  const [reason, setReason] = useState(REJECT_REASONS[0])
  const [decided, setDecided] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getIssues().then((d) => { setIssues(d.items); setTotal(d.total); setError(null) })
      .catch(() => setError('Backend not reachable — start it with: uvicorn app.main:app'))
  }, [])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    issues.forEach((i) => { c[i.kind] = (c[i.kind] ?? 0) + 1 })
    return c
  }, [issues])

  const shown = filter === 'all' ? issues : issues.filter((i) => i.kind === filter)

  const act = (issue: Issue, decision: 'approved' | 'rejected') => {
    const top = issue.options[0]
    postDecision({
      issue_id: issue.id, drug: issue.drug, location: issue.location,
      option_type: top?.type ?? '', decision, approver_role: role,
      reason: decision === 'rejected' ? reason : undefined,
    }).then(() => setDecided((d) => ({ ...d, [issue.id]: decision }))).catch(() => setError('Decision failed'))
  }

  const chip = (key: string, label: string, color: string, count: number) => (
    <button key={key} onClick={() => setFilter(key)} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, background: filter === key ? C.panelAlt : 'transparent',
      border: `1px solid ${filter === key ? color : C.border}`, borderRadius: 20, padding: '5px 12px', color: filter === key ? C.text : C.muted, fontSize: 12, cursor: 'pointer',
    }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color }} /> {label} <span className="mono" style={{ color: C.muted2 }}>{count}</span>
    </button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <div className="disp" style={{ fontSize: 18, fontWeight: 700 }}>Orchestrator</div>
        <div style={{ fontSize: 12.5, color: C.muted }}>System recommends — a human approves. Showing top {issues.length} of {total} issues.</div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>APPROVER</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} style={selStyle}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>REJECT REASON</span>
          <select value={reason} onChange={(e) => setReason(e.target.value)} style={selStyle}>{REJECT_REASONS.map((r) => <option key={r}>{r}</option>)}</select>
        </div>
      </div>

      {error && <div style={{ background: C.red + '22', border: `1px solid ${C.red}`, color: C.red, padding: '10px 12px', borderRadius: 8, fontSize: 12 }}>{error}</div>}

      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {chip('all', 'All', C.teal, issues.length)}
        {KINDS.map((k) => chip(k, kindOf(k).label, kindOf(k).color, counts[k] ?? 0))}
      </div>

      {/* Issue cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {shown.map((issue) => {
          const meta = kindOf(issue.kind)
          const status = decided[issue.id]
          return (
            <div key={issue.id} style={{ background: C.panel, border: `1px solid ${C.border}`, borderLeft: `3px solid ${meta.color}`, borderRadius: 8, padding: 14, opacity: status ? 0.7 : 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ color: meta.color, fontWeight: 700, fontSize: 12 }}>{meta.label}</span>
                <span className="disp" style={{ fontSize: 14, fontWeight: 700 }}>{issue.drug}</span>
                <span style={{ color: C.muted, fontSize: 12.5 }}>{issue.location}</span>
                <span className="mono" style={{ fontSize: 10.5, color: C.muted2, border: `1px solid ${C.border}`, borderRadius: 4, padding: '2px 7px' }}>{issue.detail}</span>
                {status && <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 700, color: status === 'approved' ? C.teal : C.red }}>
                  {status === 'approved' ? 'Approved · task created' : 'Rejected'}
                </span>}
              </div>

              {issue.options.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 10, background: C.panelAlt, borderRadius: 7, padding: 10 }}>
                  {issue.options.map((o, i) => (
                    <div key={o.type} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                      {i === 0 ? <Star size={12} color={C.amber} /> : <span style={{ width: 12 }} />}
                      {o.type === 'transfer' ? <ArrowRightLeft size={13} color={C.teal} /> : <ShoppingCart size={13} color={C.blue} />}
                      <span style={{ fontWeight: i === 0 ? 600 : 400 }}>{o.label}</span>
                      <span style={{ color: C.muted2 }}>— {o.detail}</span>
                      <span className="mono" style={{ marginLeft: 'auto', color: i === 0 ? C.teal : C.muted }}>{o.score.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}

              {!status && (
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button onClick={() => act(issue, 'approved')} disabled={!issue.options.length} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6, background: C.teal, color: '#0F141B', border: 'none',
                    borderRadius: 6, padding: '7px 14px', fontSize: 12.5, fontWeight: 700, cursor: 'pointer', opacity: issue.options.length ? 1 : 0.5,
                  }}><CheckCircle2 size={14} /> Approve{issue.options[0] ? ` ${issue.options[0].type}` : ''}</button>
                  <button onClick={() => act(issue, 'rejected')} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', color: C.red,
                    border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 12px', fontSize: 12.5, cursor: 'pointer',
                  }}><XCircle size={14} /> Reject</button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const selStyle: React.CSSProperties = {
  background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '5px 8px', fontSize: 12,
}
