import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import MenuBar from './components/MenuBar'
import Stock from './screens/Stock'
import Forecast from './screens/Forecast'
import Orchestrator from './screens/Orchestrator'
import Dashboard from './screens/Dashboard'
import Audit from './screens/Audit'
import Settings from './screens/Settings'
import { C } from './theme'

/** Centered, scrolling layout for non-sheet screens. */
function Page({ children }: { children: ReactNode }) {
  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
      <div style={{ maxWidth: 1240, margin: '0 auto', padding: '20px 20px 48px' }}>{children}</div>
    </div>
  )
}

export default function App() {
  const [clock, setClock] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: C.bg, color: C.text }}>
      <MenuBar clock={clock} />
      <main style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/stock" replace />} />
          {/* Sheet screens render full-bleed (they manage their own height). */}
          <Route path="/stock" element={<Stock />} />
          <Route path="/forecast" element={<Forecast />} />
          {/* Everything else is centered + scrollable. */}
          <Route path="/orchestrator" element={<Page><Orchestrator /></Page>} />
          <Route path="/dashboard" element={<Page><Dashboard /></Page>} />
          <Route path="/audit" element={<Page><Audit /></Page>} />
          <Route path="/settings" element={<Page><Settings /></Page>} />
          <Route path="*" element={<Navigate to="/stock" replace />} />
        </Routes>
      </main>
    </div>
  )
}
