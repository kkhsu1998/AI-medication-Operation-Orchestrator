/**
 * Forecast API — drives the Forecast tab from the real inventory data.
 */
import { cached } from '../cache'

const BASE = import.meta.env.VITE_API_URL || ''

export interface ForecastOverview {
  days: string[]
  medications: string[]
  aggregate: number[]
}

export interface ForecastItem {
  drug: string
  days: string[]
  values: number[]
}

export function getOverview(): Promise<ForecastOverview> {
  return cached('forecast:overview', async () => {
    const res = await fetch(`${BASE}/api/v1/forecast/overview`)
    if (!res.ok) throw new Error(`overview failed: ${res.status}`)
    return res.json() as Promise<ForecastOverview>
  })
}

export function getItem(drug: string): Promise<ForecastItem> {
  return cached(`forecast:item:${drug}`, async () => {
    const res = await fetch(`${BASE}/api/v1/forecast/item?drug=${encodeURIComponent(drug)}`)
    if (!res.ok) throw new Error(`item failed: ${res.status}`)
    return res.json() as Promise<ForecastItem>
  })
}

export type ModelType = 'xgboost' | 'random_forest' | 'arima' | 'moving_average'

export async function predictSeries(series: number[], steps: number, model: ModelType, lags?: number): Promise<number[]> {
  const res = await fetch(`${BASE}/api/v1/forecast/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ series, steps, model, lags }),
  })
  if (!res.ok) throw new Error(`predict failed: ${res.status}`)
  const data = await res.json()
  return data.predictions as number[]
}

// ---- Multivariate feature-lattice workbench ----
export interface FeatureOptions {
  categoricals: { column: string; encoders: string[] }[]
  calendar: string[]
  suggested_lags: number[]
  normalizers: string[]
  models: string[]
}
export const getFeatureOptions = () =>
  cached('forecast:features', async () => {
    const res = await fetch(`${BASE}/api/v1/forecast/features`)
    if (!res.ok) throw new Error(`features failed: ${res.status}`)
    return res.json() as Promise<FeatureOptions>
  })

export interface FeatureSpec {
  type: 'lag' | 'calendar' | 'categorical' | 'derived'
  lag?: number
  kind?: string
  column?: string
  encoder?: string
  name?: string
  formula?: string
}
export interface TrainResult {
  model: string
  normalization: string
  steps: number
  n_train_rows: number
  features_used: string[]
  history: { date: string; value: number }[]
  predictions: { date: string; value: number }[]
}
export async function trainForecast(
  drug: string, steps: number, model: string, normalization: string, features: FeatureSpec[],
): Promise<TrainResult> {
  const res = await fetch(`${BASE}/api/v1/forecast/train`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drug, steps, model, normalization, features }),
  })
  if (!res.ok) throw new Error(`train failed: ${res.status} ${await res.text()}`)
  return res.json()
}
