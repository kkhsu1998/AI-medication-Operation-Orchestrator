/**
 * Dashboard — operational KPIs derived live from inventory + consumption.
 */
import { useEffect, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Boxes, MapPin, Package, AlertTriangle } from 'lucide-react'
import { getDashboard, type Dashboard as Data } from '../api/platform'
import { cached } from '../cache'
import { kindOf } from '../kinds'
import { C } from '../theme'

const fmt = (n: number) => n.toLocaleString('en-US')

function Tile({ label, value, icon, tone }: { label: string; value: string; icon: React.ReactNode; tone: string }) {
  return (
    <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: tone }}>{icon}
        <span className="mono" style={{ fontSize: 10.5, color: C.muted2 }}>{label}</span>
      </div>
      <div className="disp" style={{ fontSize: 26, fontWeight: 700, color: C.text }}>{value}</div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    cached('dashboard', getDashboard).then(setData).catch(() => setError('Backend not reachable — start it with: uvicorn app.main:app'))
  }, [])

  if (error) return <div style={{ padding: 24, color: C.red }}>{error}</div>
  if (!data) return <div style={{ padding: 24, color: C.muted }}>Loading…</div>

  const trend = data.consumption_trend.map((t) => ({ day: t.day.slice(5), value: t.value }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div className="disp" style={{ fontSize: 18, fontWeight: 700 }}>Operational Dashboard</div>
        <div style={{ fontSize: 12.5, color: C.muted }}>Live KPIs computed from current inventory and consumption history.</div>
      </div>

      {/* Primary KPI tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        <Tile label="MEDICATIONS" value={fmt(data.medications)} icon={<Boxes size={15} />} tone={C.teal} />
        <Tile label="LOCATIONS" value={fmt(data.locations)} icon={<MapPin size={15} />} tone={C.blue} />
        <Tile label="UNITS ON HAND" value={fmt(data.total_units_on_hand)} icon={<Package size={15} />} tone={C.purple} />
        <Tile label="OPEN ISSUES" value={fmt(data.issues_total)} icon={<AlertTriangle size={15} />} tone={C.amber} />
      </div>

      {/* Issue breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        {['stockout', 'shortage', 'expiration_risk', 'overstock'].map((k) => {
          const meta = kindOf(k)
          return (
            <div key={k} style={{ background: C.panel, border: `1px solid ${C.border}`, borderLeft: `3px solid ${meta.color}`, borderRadius: 8, padding: '12px 14px' }}>
              <div className="mono" style={{ fontSize: 10, color: C.muted2 }}>{meta.label.toUpperCase()}</div>
              <div className="disp" style={{ fontSize: 22, fontWeight: 700, color: meta.color }}>{fmt(data.issues_by_kind[k] ?? 0)}</div>
            </div>
          )
        })}
      </div>

      {/* Consumption trend */}
      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16, height: 260 }}>
        <div className="mono" style={{ fontSize: 10.5, color: C.muted2, marginBottom: 10 }}>AGGREGATE CONSUMPTION — LAST 30 DAYS</div>
        <ResponsiveContainer width="100%" height="86%">
          <AreaChart data={trend} margin={{ top: 6, right: 20, bottom: 6, left: 0 }}>
            <defs>
              <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.teal} stopOpacity={0.4} />
                <stop offset="100%" stopColor={C.teal} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={C.border} strokeDasharray="3 3" />
            <XAxis dataKey="day" stroke={C.muted} fontSize={11} minTickGap={24} />
            <YAxis stroke={C.muted} fontSize={11} width={54} />
            <Tooltip contentStyle={{ background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontSize: 12 }} />
            <Area type="monotone" dataKey="value" stroke={C.teal} strokeWidth={2} fill="url(#g)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Top issues */}
      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
        <div className="mono" style={{ fontSize: 10.5, color: C.muted2, marginBottom: 10 }}>TOP PRIORITY ISSUES</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.top_issues.map((i) => {
            const meta = kindOf(i.kind)
            return (
              <div key={i.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 10px', background: C.panelAlt, borderRadius: 7, fontSize: 12.5 }}>
                <span style={{ minWidth: 78, color: meta.color, fontWeight: 600, fontSize: 11 }}>{meta.label}</span>
                <span style={{ fontWeight: 600 }}>{i.drug}</span>
                <span style={{ color: C.muted }}>{i.location}</span>
                <span className="mono" style={{ marginLeft: 'auto', color: C.muted2, fontSize: 11 }}>{i.detail}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
