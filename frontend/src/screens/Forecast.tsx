/**
 * Forecast tab — daily demand (2 years of history) with an interactive
 * "Predict N steps" action. Lags are by day, so weekly seasonality shows.
 *
 * Left rail selects the series (All medications = aggregate daily demand, or a
 * single drug). Pick a model (XGBoost / Random Forest / ARIMA / Moving Avg), set
 * N days, and hit Predict: the backend forecasts N days ahead, appended to the
 * table (red) and drawn as a red forecast line (history in white).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { TrendingUp, RotateCcw } from 'lucide-react'
import DataGrid from '../components/DataGrid/DataGrid'
import type { GridColumn, Row } from '../components/DataGrid/xlsx'
import { getItem, getOverview, predictSeries, type ForecastOverview, type ModelType } from '../api/forecast'
import { C } from '../theme'

const MON_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const label = (iso: string) => {
  const [, m, d] = iso.split('-')
  return `${MON_ABBR[Number(m) - 1]} ${Number(d)}`
}
const nextDay = (iso: string) => {
  const dt = new Date(iso + 'T00:00:00Z')
  dt.setUTCDate(dt.getUTCDate() + 1)
  return dt.toISOString().slice(0, 10)
}
const AGG = 'ALL'

const MODELS: { k: ModelType; label: string }[] = [
  { k: 'xgboost', label: 'XGBoost' },
  { k: 'random_forest', label: 'Random Forest' },
  { k: 'arima', label: 'ARIMA' },
  { k: 'moving_average', label: 'Moving Avg' },
]

interface Point { date: string; value: number }

export default function Forecast() {
  const [overview, setOverview] = useState<ForecastOverview | null>(null)
  const [selected, setSelected] = useState<string>(AGG)
  const [base, setBase] = useState<Point[]>([])
  const [predictions, setPredictions] = useState<Point[]>([])
  const [model, setModel] = useState<ModelType>('xgboost')
  const [steps, setSteps] = useState(14)
  const [lags, setLags] = useState(14)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartFrac, setChartFrac] = useState(0.55) // width fraction of the chart pane

  const splitRef = useRef<HTMLDivElement>(null)

  const isAll = selected === AGG

  const startDrag = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const onMove = (ev: MouseEvent) => {
      const el = splitRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const frac = (ev.clientX - rect.left) / rect.width
      setChartFrac(Math.max(0.2, Math.min(0.8, frac)))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [])

  useEffect(() => {
    getOverview()
      .then((o) => { setOverview(o); setError(null) })
      .catch(() => setError('Backend not reachable — start it with: uvicorn app.main:app'))
  }, [])

  useEffect(() => {
    setPredictions([])
    if (!overview) return
    if (isAll) {
      setBase(overview.days.map((d, i) => ({ date: d, value: overview.aggregate[i] })))
      return
    }
    getItem(selected)
      .then((it) => { setBase(it.days.map((d, i) => ({ date: d, value: it.values[i] }))); setError(null) })
      .catch(() => setError(`Could not load history for ${selected}`))
  }, [selected, isAll, overview])

  const grouped = useMemo(() => {
    const g: Record<string, string[]> = {}
    ;(overview?.medications ?? []).forEach((d) => { (g[d[0].toUpperCase()] ||= []).push(d) })
    return g
  }, [overview])

  const runPredict = () => {
    const series = base.map((p) => p.value)
    if (series.length < 2) { setError('Need at least 2 history points to predict'); return }
    setBusy(true)
    predictSeries(series, steps, model, lags)
      .then((preds) => {
        let d = base[base.length - 1].date
        setPredictions(preds.map((v) => { d = nextDay(d); return { date: d, value: v } }))
        setError(null)
      })
      .catch(() => setError('Prediction failed'))
      .finally(() => setBusy(false))
  }

  const columns: GridColumn[] = [
    { key: 'date', name: 'Date', width: 130, editable: false },
    { key: 'demand', name: isAll ? 'Total demand' : 'Demand', width: 150, editable: false },
    { key: 'kind', name: 'Type', width: 110, editable: false },
  ]
  const rows: Row[] = [
    ...base.map((p) => ({ date: p.date, demand: p.value, kind: 'actual' })),
    ...predictions.map((p) => ({ date: p.date, demand: p.value, kind: 'forecast' })),
  ]

  const chartData = [
    ...base.map((p, i) => ({ date: label(p.date), Actual: p.value, Forecast: i === base.length - 1 ? p.value : null })),
    ...predictions.map((p) => ({ date: label(p.date), Actual: null, Forecast: p.value })),
  ]

  const railItem = (name: string, active: boolean, onClick: () => void, sub?: string) => (
    <button key={name} onClick={onClick} style={{
      display: 'block', width: '100%', textAlign: 'left',
      background: active ? C.panelAlt : 'transparent', border: `1px solid ${active ? C.teal : 'transparent'}`,
      borderRadius: 7, padding: '8px 10px', color: active ? C.text : C.muted, fontSize: 12.5, fontWeight: active ? 600 : 400, cursor: 'pointer',
    }}>
      {name}{sub && <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>{sub}</div>}
    </button>
  )

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
      <aside style={{ width: 232, flexShrink: 0, borderRight: `1px solid ${C.border}`, background: C.panel, overflowY: 'auto', padding: 12 }}>
        <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '2px 0 8px' }}>VIEW</div>
        {railItem('All medications', isAll, () => setSelected(AGG), 'aggregate · daily')}
        <div className="mono" style={{ fontSize: 9.5, color: C.muted2, margin: '14px 0 6px' }}>
          MEDICATIONS{overview ? ` (${overview.medications.length})` : ''}
        </div>
        {Object.keys(grouped).sort().map((letter) => (
          <div key={letter} style={{ marginBottom: 6 }}>
            <div className="disp" style={{ fontSize: 11, color: C.muted2, padding: '2px 10px' }}>{letter}</div>
            {grouped[letter].map((drug) => railItem(drug, selected === drug, () => setSelected(drug)))}
          </div>
        ))}
      </aside>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 16px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <div className="disp" style={{ fontSize: 17, fontWeight: 700 }}>Forecast — {isAll ? 'All medications' : selected}</div>
          <div style={{ fontSize: 12, color: C.muted }}>Daily demand · pick a model, set steps (days), and Predict — forecast rows are red.</div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '8px 10px' }}>
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>MODEL</span>
          {MODELS.map((m) => (
            <button key={m.k} onClick={() => setModel(m.k)} style={{
              background: model === m.k ? C.teal : C.panelAlt, color: model === m.k ? '#0F141B' : C.text,
              border: `1px solid ${model === m.k ? C.teal : C.border}`, borderRadius: 6, padding: '6px 11px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>{m.label}</button>
          ))}
          <div style={{ width: 1, height: 22, background: C.border, margin: '0 4px' }} />
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>DAYS</span>
          <input type="number" min={1} max={365} value={steps} onChange={(e) => setSteps(Math.max(1, Math.min(365, Number(e.target.value) || 1)))}
            style={{ width: 64, background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', fontSize: 12 }} />
          <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>LAGS</span>
          <input type="number" min={1} max={60} value={lags} onChange={(e) => setLags(Math.max(1, Math.min(60, Number(e.target.value) || 1)))}
            style={{ width: 64, background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', fontSize: 12 }} />
          <button onClick={runPredict} disabled={busy || base.length < 2} style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, background: C.teal, color: '#0F141B', border: 'none',
            borderRadius: 6, padding: '7px 14px', fontSize: 12.5, fontWeight: 700, cursor: busy ? 'wait' : 'pointer', opacity: base.length < 2 ? 0.5 : 1,
          }}><TrendingUp size={14} /> {busy ? 'Predicting…' : `Predict ${steps} days`}</button>
          {predictions.length > 0 && (
            <button onClick={() => setPredictions([])} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', color: C.muted,
              border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 11px', fontSize: 12, cursor: 'pointer',
            }}><RotateCcw size={13} /> Reset</button>
          )}
        </div>

        {error && <div style={{ background: C.red + '22', border: `1px solid ${C.red}`, color: C.red, padding: '9px 12px', borderRadius: 8, fontSize: 12 }}>{error}</div>}

        <div ref={splitRef} style={{ flex: 1, minHeight: 280, display: 'flex', alignItems: 'stretch' }}>
          {/* Chart pane (LEFT) */}
          <div style={{ flexBasis: `${chartFrac * 100}%`, flexGrow: 0, flexShrink: 0, minWidth: 0, display: 'flex', flexDirection: 'column', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '12px 16px 8px' }}>
            <div className="mono" style={{ fontSize: 10.5, color: C.muted2, marginBottom: 10 }}>DAILY DEMAND — ACTUAL vs FORECAST ({model})</div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 6, right: 24, bottom: 6, left: 0 }}>
                  <CartesianGrid stroke={C.border} strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke={C.muted} fontSize={11} minTickGap={48} />
                  <YAxis stroke={C.muted} fontSize={11} width={54} />
                  <Tooltip contentStyle={{ background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="Actual" stroke="#FFFFFF" strokeWidth={1.8} dot={false} connectNulls isAnimationActive={false} />
                  <Line type="monotone" dataKey="Forecast" stroke={C.red} strokeWidth={2.2} strokeDasharray="6 3" dot={false} connectNulls isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Draggable vertical divider */}
          <div
            onMouseDown={startDrag}
            role="separator"
            aria-orientation="vertical"
            style={{ flex: '0 0 10px', cursor: 'col-resize', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <div style={{ width: 3, height: '100%', borderRadius: 3, background: C.border }} />
          </div>

          {/* Excel table pane (RIGHT) */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            <DataGrid
              key={selected}
              columns={columns}
              rows={rows}
              onRowsChange={() => {}}
              name={isAll ? 'forecast-all' : `forecast-${selected.split(' ')[0].toLowerCase()}`}
              emptyRow={() => ({ date: '', demand: '', kind: '' })}
              minRows={Math.max(rows.length, 6)}
              rowClass={(r) => (r.kind === 'forecast' ? 'rdg-forecast' : undefined)}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
