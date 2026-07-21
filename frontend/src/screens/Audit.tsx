/**
 * Audit — the immutable trail of consequential actions (who, when, what, why).
 */
import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, ScrollText } from 'lucide-react'
import { getAudit, type AuditEntry } from '../api/platform'
import { cached, invalidate } from '../cache'
import { C } from '../theme'

const ACTION_COLOR: Record<string, string> = {
  'orchestrator.approve': C.teal,
  'orchestrator.reject': C.red,
  'task.create': C.blue,
  'settings.update': C.amber,
  'stock.save': C.muted,
}

export default function Audit() {
  const [items, setItems] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    cached('audit', () => getAudit(200)).then((d) => { setItems(d.items); setTotal(d.total); setError(null) })
      .catch(() => setError('Backend not reachable — start it with: uvicorn app.main:app'))
  }, [])

  // Refresh bypasses the cache: drop the entry, then reload fresh (repopulating it).
  const refresh = useCallback(() => { invalidate('audit'); load() }, [load])

  useEffect(() => { load() }, [load])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <div className="disp" style={{ fontSize: 18, fontWeight: 700 }}>Audit Trail</div>
        <div style={{ fontSize: 12.5, color: C.muted }}>Every decision retained — {total} record{total === 1 ? '' : 's'}.</div>
        <button onClick={refresh} style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6, background: C.panelAlt, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 11px', fontSize: 12, cursor: 'pointer' }}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {error && <div style={{ background: C.red + '22', border: `1px solid ${C.red}`, color: C.red, padding: '10px 12px', borderRadius: 8, fontSize: 12 }}>{error}</div>}

      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '150px 150px 110px 170px 1fr', gap: 0, background: C.panelAlt, padding: '9px 14px', borderBottom: `1px solid ${C.border}` }}
          className="mono" >
          {['CHANGE POINT', 'TIME', 'ACTOR', 'ACTION', 'DETAIL'].map((h) => <span key={h} style={{ fontSize: 10, color: C.muted2 }}>{h}</span>)}
        </div>
        {items.length === 0 && <div style={{ padding: 24, textAlign: 'center', color: C.muted2, fontSize: 12.5 }}>
          <ScrollText size={22} style={{ opacity: 0.5, marginBottom: 6 }} /><div>No actions recorded yet. Approve an issue or edit settings to see entries here.</div>
        </div>}
        {items.map((a) => (
          <div key={a.id} style={{ display: 'grid', gridTemplateColumns: '150px 150px 110px 170px 1fr', gap: 0, padding: '9px 14px', borderBottom: `1px solid ${C.border}`, fontSize: 12.5 }}>
            <span className="mono" style={{ color: a.action.startsWith('mcp.') ? C.teal : C.muted2, fontSize: 11, fontWeight: 600 }}>{a.change_id || '—'}</span>
            <span className="mono" style={{ color: C.muted2, fontSize: 11 }}>{a.ts.slice(0, 19).replace('T', ' ')}</span>
            <span style={{ color: C.text }}>{a.actor}</span>
            <span className="mono" style={{ fontSize: 11, color: ACTION_COLOR[a.action] ?? (a.action.startsWith('mcp.') ? C.teal : C.muted), fontWeight: 600 }}>{a.action}</span>
            <span style={{ color: C.muted }}>{a.detail}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
