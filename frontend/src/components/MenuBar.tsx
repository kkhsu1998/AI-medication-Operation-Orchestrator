/**
 * Top bar + tab navigation. Tabs are real routes (react-router).
 */
import { NavLink } from 'react-router-dom'
import {
  ShieldCheck,
  Boxes,
  TrendingUp,
  Workflow,
  BarChart3,
  ScrollText,
  Settings,
} from 'lucide-react'
import { C } from '../theme'

const TABS = [
  { to: '/stock', label: 'Stock', icon: Boxes },
  { to: '/forecast', label: 'Forecast', icon: TrendingUp },
  { to: '/orchestrator', label: 'Orchestrator', icon: Workflow },
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/audit', label: 'Audit', icon: ScrollText },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function MenuBar({ clock }: { clock: Date }) {
  return (
    <header
      style={{
        borderBottom: `1px solid ${C.border}`,
        background: C.panel,
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      {/* Brand row */}
      <div
        style={{
          padding: '12px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldCheck size={22} color={C.teal} />
          <div>
            <div className="disp" style={{ fontSize: 16, fontWeight: 700 }}>
              MedOps Orchestrator
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: C.muted }}>
              stock • forecast • ranked options • human approval
            </div>
          </div>
        </div>
        <div className="mono" style={{ fontSize: 12, color: C.muted }}>
          {clock.toLocaleTimeString('en-US', { hour12: false })}
        </div>
      </div>

      {/* Tabs */}
      <nav style={{ display: 'flex', gap: 2, padding: '0 12px', flexWrap: 'wrap' }}>
        {TABS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '9px 14px',
              fontSize: 13,
              fontWeight: 600,
              color: isActive ? C.text : C.muted,
              borderBottom: `2px solid ${isActive ? C.teal : 'transparent'}`,
              textDecoration: 'none',
            })}
          >
            <Icon size={15} /> {label}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}
