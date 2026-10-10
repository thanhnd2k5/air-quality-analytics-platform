import { apiGet } from './client'

export type PredictionMeta = {
  data_min: string
  data_max: string
  default_from: string
  default_to: string
  model_versions: string[]
}

export type PredictionMetrics = {
  split: string
  n: number
  mae_model: number | null
  mae_persistence: number | null
}

export type PredictionPoint = {
  target_time: string
  actual_pm25: number | null
  predicted_pm25: number | null
  predicted_pm25_persistence: number | null
  absolute_error: number | null
  split: string
}

export type PredictionsResponse = {
  date_from: string
  date_to: string
  station_key: number | null
  split: string | null
  model_version: string | null
  metrics: PredictionMetrics[]
  series: PredictionPoint[]
}

export function fetchPredictionMeta() {
  return apiGet<PredictionMeta>('/api/predictions/meta')
}

export function fetchPredictions(opts: {
  date_from?: string
  date_to?: string
  station_key?: number | null
  split?: string | null
}) {
  const sp = new URLSearchParams()
  if (opts.date_from) sp.set('date_from', opts.date_from)
  if (opts.date_to) sp.set('date_to', opts.date_to)
  if (opts.station_key != null) sp.set('station_key', String(opts.station_key))
  if (opts.split) sp.set('split', opts.split)
  const q = sp.toString()
  return apiGet<PredictionsResponse>(`/api/predictions${q ? `?${q}` : ''}`)
}
