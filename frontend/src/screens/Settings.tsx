/**
 * Settings — edit operational configuration (safety stock, thresholds, scoring
 * weights). Changes persist to the DB and are recorded in the audit trail.
 */
import { useEffect, useMemo, useState } from 'react'
import { Save } from 'lucide-react'
import { getSettings, patchSettings, type SettingItem } from '../api/platform'
import { cached, invalidate } from '../cache'
import { C } from '../theme'

type Status = 'idle' | 'saving' | 'saved' | 'error'

export default function Settings() {
  const [items, setItems] = useState<SettingItem[]>([])
  const [draft, setDraft] = useState<Record<string, number>>({})
  const [status, setStatus] = useState<Status>('idle')

  useEffect(() => {
    cached('settings', getSettings).then((d) => {
      setItems(d.items)
      setDraft(Object.fromEntries(d.items.map((i) => [i.key, i.value])))
    }).catch(() => setStatus('error'))
  }, [])

  const groups = useMemo(() => {
    const g: Record<string, SettingItem[]> = {}
    items.forEach((i) => { (g[i.group] ||= []).push(i) })
    return g
  }, [items])

  const dirty = items.some((i) => draft[i.key] !== i.value)

  const save = () => {
    setStatus('saving')
    patchSettings(draft).then((d) => {
      setItems(d.items)
      setDraft(Object.fromEntries(d.items.map((i) => [i.key, i.value])))
      // Refresh cached settings + dashboard (thresholds affect its KPIs) on next visit.
      invalidate('settings')
      invalidate('dashboard')
      setStatus('saved')
    }).catch(() => setStatus('error'))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <div className="disp" style={{ fontSize: 18, fontWeight: 700 }}>Settings</div>
        <div style={{ fontSize: 12.5, color: C.muted }}>Operational thresholds and scoring weights. Persisted + audited.</div>
      </div>

      {Object.keys(groups).map((group) => (
        <div key={group} style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
          <div className="mono" style={{ fontSize: 10.5, color: C.muted2, marginBottom: 12 }}>{group.toUpperCase()}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {groups[group].map((i) => (
              <div key={i.key} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <label style={{ flex: 1, fontSize: 13 }}>{i.label}
                  <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>{i.key}</div>
                </label>
                <input
                  type="number" step="0.1"
                  value={draft[i.key] ?? ''}
                  onChange={(e) => setDraft({ ...draft, [i.key]: Number(e.target.value) })}
                  style={{ width: 110, background: C.bg, color: C.text, border: `1px solid ${draft[i.key] !== i.value ? C.amber : C.border}`, borderRadius: 6, padding: '7px 9px', fontSize: 13, textAlign: 'right' }}
                />
              </div>
            ))}
          </div>
        </div>
      ))}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={save} disabled={!dirty || status === 'saving'} style={{
          display: 'inline-flex', alignItems: 'center', gap: 7, background: dirty ? C.teal : C.panelAlt, color: dirty ? '#0F141B' : C.muted,
          border: 'none', borderRadius: 7, padding: '9px 18px', fontSize: 13, fontWeight: 700, cursor: dirty ? 'pointer' : 'default',
        }}><Save size={15} /> {status === 'saving' ? 'Saving…' : 'Save changes'}</button>
        {status === 'saved' && !dirty && <span className="mono" style={{ fontSize: 11.5, color: C.teal }}>Saved to database</span>}
        {status === 'error' && <span className="mono" style={{ fontSize: 11.5, color: C.red }}>Backend not reachable</span>}
      </div>
    </div>
  )
}
