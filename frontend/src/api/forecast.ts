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
