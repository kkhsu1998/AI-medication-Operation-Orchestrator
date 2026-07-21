/**
 * Forecast tab — daily demand (2 years of history) with an interactive
 * "Predict N steps" action. Lags are by day, so weekly seasonality shows.
 *
 * Left rail selects the series (All medications = aggregate daily demand, or a
 * single drug). Pick a model (XGBoost / Random Forest / ARIMA / Moving Avg), set
 * N days, and hit Predict: the backend forecasts N days ahead, appended to the
 * table (red) and drawn as a red forecast line (history in white).
 *
 * Two modes:
 *  - "Predict" (simple): the original univariate flow (predictSeries).
 *  - "Feature Lattice": a multivariate workbench where you compose FeatureSpecs
 *    (lags, calendar, categorical encodings, derived formula columns) and call
 *    trainForecast on a single drug.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { TrendingUp, RotateCcw, Plus, X } from 'lucide-react'
import DataGrid from '../components/DataGrid/DataGrid'
import type { GridColumn, Row } from '../components/DataGrid/xlsx'
import {
  getItem, getOverview, predictSeries, getFeatureOptions, trainForecast,
  type ForecastOverview, type ModelType, type FeatureOptions, type FeatureSpec, type TrainResult,
} from '../api/forecast'
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

const MODEL_LABEL: Record<string, string> = {
  xgboost: 'XGBoost',
  random_forest: 'Random Forest',
  arima: 'ARIMA',
  moving_average: 'Moving Avg',
}

type Mode = 'predict' | 'lattice'

const DEFAULT_LATTICE: FeatureSpec[] = [
  { type: 'lag', lag: 1 },
  { type: 'lag', lag: 7 },
  { type: 'calendar', kind: 'dow' },
  { type: 'categorical', column: 'location', encoder: 'onehot' },
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

  // ---- Feature Lattice mode state ----
  const [mode, setMode] = useState<Mode>('predict')
  const [options, setOptions] = useState<FeatureOptions | null>(null)
  const [normalization, setNormalization] = useState('standard')
  const [featureSpecs, setFeatureSpecs] = useState<FeatureSpec[]>(DEFAULT_LATTICE)
  const [trained, setTrained] = useState<TrainResult | null>(null)
  // add-feature control inputs
  const [newLag, setNewLag] = useState(1)
  const [newCalendar, setNewCalendar] = useState('')
  const [derivedName, setDerivedName] = useState('')
  const [derivedFormula, setDerivedFormula] = useState('')

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
    getFeatureOptions()
      .then((o) => {
        setOptions(o)
        setNewCalendar(o.calendar[0] ?? '')
        setNewLag(o.suggested_lags[0] ?? 1)
        if (o.normalizers.length && !o.normalizers.includes(normalization)) setNormalization(o.normalizers[0])
      })
      .catch(() => { /* options are optional; lattice mode will show a hint */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setPredictions([])
    setTrained(null)
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

  const runTrain = () => {
    if (isAll) return
    setBusy(true)
    setError(null)
    trainForecast(selected, steps, model, normalization, featureSpecs)
      .then((res) => { setTrained(res); setError(null) })
      .catch((e) => { setTrained(null); setError(`Train failed: ${e instanceof Error ? e.message : String(e)}`) })
      .finally(() => setBusy(false))
  }

  // Lattice model options (only tree models support the feature lattice)
  const latticeModels = options?.models?.length
    ? options.models.filter((m) => m === 'xgboost' || m === 'random_forest')
    : ['xgboost', 'random_forest']

  // Ensure the active model is valid for lattice mode
  useEffect(() => {
    if (mode === 'lattice' && !latticeModels.includes(model)) {
      setModel((latticeModels[0] as ModelType) ?? 'xgboost')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const addFeature = (f: FeatureSpec) => setFeatureSpecs((prev) => [...prev, f])
  const removeFeature = (i: number) => setFeatureSpecs((prev) => prev.filter((_, idx) => idx !== i))

  const featureLabel = (f: FeatureSpec): { type: string; params: string } => {
    switch (f.type) {
      case 'lag': return { type: 'lag', params: `lag_${f.lag}` }
      case 'calendar': return { type: 'calendar', params: `cal_${f.kind}` }
      case 'categorical': return { type: 'categorical', params: `${f.column} · ${f.encoder}` }
      case 'derived': return { type: 'derived', params: `${f.name} = ${f.formula}` }
      default: return { type: f.type, params: '' }
    }
  }

  // ---- Table pane data (Predict mode) ----
  const columns: GridColumn[] = [
    { key: 'date', name: 'Date', width: 130, editable: false },
    { key: 'demand', name: isAll ? 'Total demand' : 'Demand', width: 150, editable: false },
    { key: 'kind', name: 'Type', width: 110, editable: false },
  ]
  const rows: Row[] = [
    ...base.map((p) => ({ date: p.date, demand: p.value, kind: 'actual' })),
    ...predictions.map((p) => ({ date: p.date, demand: p.value, kind: 'forecast' })),
  ]

  // ---- Chart data (mode-dependent) ----
  const predictChartData = [
    ...base.map((p, i) => ({ date: label(p.date), Actual: p.value, Forecast: i === base.length - 1 ? p.value : null })),
    ...predictions.map((p) => ({ date: label(p.date), Actual: null, Forecast: p.value })),
  ]
  const latticeChartData = trained
    ? [
        ...trained.history.map((p, i) => ({
          date: label(p.date), Actual: p.value,
          Forecast: i === trained.history.length - 1 ? p.value : null,
        })),
        ...trained.predictions.map((p) => ({ date: label(p.date), Actual: null, Forecast: p.value })),
      ]
    : []
  const chartData = mode === 'lattice' ? latticeChartData : predictChartData

  const railItem = (name: string, active: boolean, onClick: () => void, sub?: string) => (
    <button key={name} onClick={onClick} style={{
      display: 'block', width: '100%', textAlign: 'left',
      background: active ? C.panelAlt : 'transparent', border: `1px solid ${active ? C.teal : 'transparent'}`,
      borderRadius: 7, padding: '8px 10px', color: active ? C.text : C.muted, fontSize: 12.5, fontWeight: active ? 600 : 400, cursor: 'pointer',
    }}>
      {name}{sub && <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>{sub}</div>}
    </button>
  )

  const selStyle: React.CSSProperties = {
    background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', fontSize: 12,
  }
  const smallBtn = (extra?: React.CSSProperties): React.CSSProperties => ({
    display: 'inline-flex', alignItems: 'center', gap: 4, background: C.panelAlt, color: C.text,
    border: `1px solid ${C.border}`, borderRadius: 6, padding: '5px 9px', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', ...extra,
  })

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div className="disp" style={{ fontSize: 17, fontWeight: 700 }}>Forecast — {isAll ? 'All medications' : selected}</div>
          <div style={{ fontSize: 12, color: C.muted, flex: 1, minWidth: 120 }}>
            {mode === 'lattice'
              ? 'Compose features, train a multivariate model on one medication, and forecast.'
              : 'Daily demand · pick a model, set steps (days), and Predict — forecast rows are red.'}
          </div>
          {/* Segmented mode toggle */}
          <div style={{ display: 'inline-flex', background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 8, padding: 2 }}>
            {([['predict', 'Predict'], ['lattice', 'Feature Lattice']] as [Mode, string][]).map(([m, lbl]) => (
              <button key={m} onClick={() => { setMode(m); setError(null) }} style={{
                background: mode === m ? C.teal : 'transparent', color: mode === m ? '#0F141B' : C.muted,
                border: 'none', borderRadius: 6, padding: '6px 12px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
              }}>{lbl}</button>
            ))}
          </div>
        </div>

        {/* ---- Controls row ---- */}
        {mode === 'predict' ? (
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
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '8px 10px' }}>
            <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>MODEL</span>
            {latticeModels.map((m) => (
              <button key={m} onClick={() => setModel(m as ModelType)} style={{
                background: model === m ? C.teal : C.panelAlt, color: model === m ? '#0F141B' : C.text,
                border: `1px solid ${model === m ? C.teal : C.border}`, borderRadius: 6, padding: '6px 11px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}>{MODEL_LABEL[m] ?? m}</button>
            ))}
            <div style={{ width: 1, height: 22, background: C.border, margin: '0 4px' }} />
            <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>NORM</span>
            <select value={normalization} onChange={(e) => setNormalization(e.target.value)} style={selStyle}>
              {(options?.normalizers ?? ['none', 'standard', 'minmax']).map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>STEPS</span>
            <input type="number" min={1} max={365} value={steps} onChange={(e) => setSteps(Math.max(1, Math.min(365, Number(e.target.value) || 1)))}
              style={{ width: 64, background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 8px', fontSize: 12 }} />
            <button onClick={runTrain} disabled={busy || isAll || featureSpecs.length === 0} title={isAll ? 'Pick a single medication for the feature lattice' : undefined} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, background: C.teal, color: '#0F141B', border: 'none',
              borderRadius: 6, padding: '7px 14px', fontSize: 12.5, fontWeight: 700, cursor: busy ? 'wait' : (isAll ? 'not-allowed' : 'pointer'),
              opacity: (isAll || featureSpecs.length === 0) ? 0.5 : 1,
            }}><TrendingUp size={14} /> {busy ? 'Training…' : 'Train & Forecast'}</button>
            {isAll && <span style={{ fontSize: 11, color: C.amber }}>Pick a single medication for the feature lattice</span>}
            {trained && (
              <>
                <div style={{ width: 1, height: 22, background: C.border, margin: '0 4px' }} />
                <span className="mono" style={{ fontSize: 10.5, color: C.muted }}>{trained.n_train_rows} train rows</span>
              </>
            )}
          </div>
        )}

        {/* features_used chips (lattice, after successful train) */}
        {mode === 'lattice' && trained && trained.features_used.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>FEATURES USED</span>
            {trained.features_used.map((f) => (
              <span key={f} className="mono" style={{
                fontSize: 10.5, color: C.teal, background: C.teal + '18', border: `1px solid ${C.teal}55`,
                borderRadius: 5, padding: '2px 7px',
              }}>{f}</span>
            ))}
          </div>
        )}

        {error && <div style={{ background: C.red + '22', border: `1px solid ${C.red}`, color: C.red, padding: '9px 12px', borderRadius: 8, fontSize: 12 }}>{error}</div>}

        <div ref={splitRef} style={{ flex: 1, minHeight: 280, display: 'flex', alignItems: 'stretch' }}>
          {/* Chart pane (LEFT) */}
          <div style={{ flexBasis: `${chartFrac * 100}%`, flexGrow: 0, flexShrink: 0, minWidth: 0, display: 'flex', flexDirection: 'column', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, padding: '12px 16px 8px' }}>
            <div className="mono" style={{ fontSize: 10.5, color: C.muted2, marginBottom: 10 }}>
              DAILY DEMAND — ACTUAL vs FORECAST ({MODEL_LABEL[model] ?? model})
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              {mode === 'lattice' && !trained ? (
                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.muted2, fontSize: 12.5, textAlign: 'center', padding: 20 }}>
                  Compose a feature lattice on the right, then hit “Train & Forecast”.
                </div>
              ) : (
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
              )}
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

          {/* RIGHT pane — Excel table (Predict) or Feature Lattice editor (Lattice) */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            {mode === 'predict' ? (
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
            ) : (
              <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden' }}>
                {/* Add-feature toolbar */}
                <div style={{ borderBottom: `1px solid ${C.border}`, padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>ADD FEATURE</div>
                  {/* Lag */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11.5, color: C.muted, width: 74 }}>Lag</span>
                    <input type="number" min={1} max={90} value={newLag}
                      onChange={(e) => setNewLag(Math.max(1, Math.min(90, Number(e.target.value) || 1)))}
                      style={{ ...selStyle, width: 60 }} />
                    <button onClick={() => addFeature({ type: 'lag', lag: newLag })} style={smallBtn()}><Plus size={12} /> lag_{newLag}</button>
                    {options && options.suggested_lags.length > 0 && (
                      <span className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>suggested: {options.suggested_lags.join(', ')}</span>
                    )}
                  </div>
                  {/* Calendar */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11.5, color: C.muted, width: 74 }}>Calendar</span>
                    <select value={newCalendar} onChange={(e) => setNewCalendar(e.target.value)} style={{ ...selStyle, minWidth: 90 }}>
                      {(options?.calendar ?? ['dow', 'month', 'day']).map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                    <button onClick={() => newCalendar && addFeature({ type: 'calendar', kind: newCalendar })} style={smallBtn()}><Plus size={12} /> cal_{newCalendar}</button>
                  </div>
                  {/* Categorical (per column) */}
                  {(options?.categoricals ?? [{ column: 'location', encoders: ['onehot', 'ordinal'] }]).map((cat) => (
                    <CategoricalAdder key={cat.column} column={cat.column} encoders={cat.encoders} selStyle={selStyle} smallBtn={smallBtn} onAdd={addFeature} />
                  ))}
                  {/* Derived column */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11.5, color: C.muted, width: 74 }}>Derived</span>
                    <input placeholder="name" value={derivedName} onChange={(e) => setDerivedName(e.target.value)} style={{ ...selStyle, width: 90 }} />
                    <input placeholder="lag_1 * 0.5 + lag_7" value={derivedFormula} onChange={(e) => setDerivedFormula(e.target.value)} style={{ ...selStyle, flex: 1, minWidth: 140 }} />
                    <button
                      onClick={() => {
                        if (!derivedName.trim() || !derivedFormula.trim()) return
                        addFeature({ type: 'derived', name: derivedName.trim(), formula: derivedFormula.trim() })
                        setDerivedName(''); setDerivedFormula('')
                      }}
                      style={smallBtn()}
                    ><Plus size={12} /> add</button>
                  </div>
                  <div className="mono" style={{ fontSize: 9.5, color: C.muted2 }}>
                    Formulas reference other feature columns (lag_1, lag_7, cal_dow, …).
                  </div>
                </div>

                {/* Feature list */}
                <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 10 }}>
                  <div className="mono" style={{ fontSize: 9.5, color: C.muted2, marginBottom: 8 }}>FEATURE LATTICE ({featureSpecs.length})</div>
                  {featureSpecs.length === 0 && <div style={{ fontSize: 12, color: C.muted2 }}>No features — add at least one above.</div>}
                  {featureSpecs.map((f, i) => {
                    const fl = featureLabel(f)
                    return (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 8, background: C.panelAlt, border: `1px solid ${C.border}`,
                        borderRadius: 6, padding: '6px 8px', marginBottom: 6,
                      }}>
                        <span className="mono" style={{ fontSize: 9.5, color: C.muted2, width: 78, flexShrink: 0, textTransform: 'uppercase' }}>{fl.type}</span>
                        <span className="mono" style={{ fontSize: 12, color: C.text, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{fl.params}</span>
                        <button onClick={() => removeFeature(i)} title="Remove" style={{
                          background: 'transparent', border: 'none', color: C.muted, cursor: 'pointer', display: 'inline-flex', padding: 2,
                        }}><X size={14} /></button>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// --- Categorical add-row (one encoder dropdown per categorical column) ---
function CategoricalAdder({
  column, encoders, selStyle, smallBtn, onAdd,
}: {
  column: string
  encoders: string[]
  selStyle: React.CSSProperties
  smallBtn: (extra?: React.CSSProperties) => React.CSSProperties
  onAdd: (f: FeatureSpec) => void
}) {
  const [encoder, setEncoder] = useState(encoders[0] ?? 'onehot')
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 11.5, color: C.muted, width: 74 }}>{column}</span>
      <select value={encoder} onChange={(e) => setEncoder(e.target.value)} style={{ ...selStyle, minWidth: 90 }}>
        {encoders.map((enc) => <option key={enc} value={enc}>{enc}</option>)}
      </select>
      <button onClick={() => onAdd({ type: 'categorical', column, encoder })} style={smallBtn()}>
        <Plus size={12} /> {column}
      </button>
    </div>
  )
}
