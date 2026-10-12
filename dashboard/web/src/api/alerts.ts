import { apiGet } from './client'

export type ConfusionMatrix = {
  tp: number
  fp: number
  fn: number
  tn: number
  accuracy: number | null
  precision: number | null
  recall: number | null
  f1: number | null
  onsets: number
  onsets_detected: number
}

export type StationAlertMetrics = {
  station_key: number
  station_name: string
  positives: number
  f1_model: number | null
  f1_persistence: number | null
  recall_model: number | null
  recall_persistence: number | null
}

export type AlertSummary = {
  split: string
  model_version: string | null
  alert_threshold: number | null
  probability_cutoff: number | null
  n: number
  model: ConfusionMatrix
  persistence: ConfusionMatrix
  stations: StationAlertMetrics[]
}

export type AlertMeta = {
  data_min: string
  data_max: string
  default_from: string
  default_to: string
}

export type AlertPoint = {
  target_time: string
  actual_pm25: number | null
  predicted_proba: number | null
  actual_alert: number
  predicted_alert: number
  persistence_alert: number
  outcome: string
}

export type AlertTimeline = {
  station_key: number
  date_from: string
  date_to: string
  probability_cutoff: number | null
  alert_threshold: number | null
  series: AlertPoint[]
}

export function fetchAlertMeta() {
  return apiGet<AlertMeta>('/api/alerts/meta')
}

export function fetchAlertSummary(split = 'test') {
  return apiGet<AlertSummary>(`/api/alerts/summary?split=${split}`)
}

export function fetchAlertTimeline(opts: { station_key: number; date_from?: string; date_to?: string }) {
  const sp = new URLSearchParams()
  sp.set('station_key', String(opts.station_key))
  if (opts.date_from) sp.set('date_from', opts.date_from)
  if (opts.date_to) sp.set('date_to', opts.date_to)
  return apiGet<AlertTimeline>(`/api/alerts/timeline?${sp.toString()}`)
}
