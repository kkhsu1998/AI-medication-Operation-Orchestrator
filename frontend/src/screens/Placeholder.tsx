import { C } from '../theme'

/** Simple stub for tabs that are wired into the nav but not built out yet. */
export default function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: 40,
        textAlign: 'center',
        color: C.muted,
      }}
    >
      <div className="disp" style={{ fontSize: 18, fontWeight: 700, color: C.text, marginBottom: 8 }}>
        {title}
      </div>
      <div style={{ fontSize: 13 }}>{note}</div>
    </div>
  )
}
