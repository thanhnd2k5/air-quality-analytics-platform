import { apiGet } from './client'

export type OverviewMeta = {
  data_min: string
  data_max: string
  default_from: string
  default_to: string
}

export type OverviewKpis = {
  date_from: string
  date_to: string
  station_key: number | null
  pm25_avg: number | null
  pm10_avg: number | null
  o3_avg: number | null
  so2_avg: number | null
  no2_avg: number | null
  co_avg: number | null
  station_day_rows: number
  pm25_day_rows: number
  days_pm25_ge_115: number
  episode_count: number
  duration_hours_avg: number | null
  duration_hours_max: number | null
  multi_station_event_count: number | null
}

export type TrendPoint = {
  date_day: string
  pm25_ug_m3_avg: number | null
  pm10_ug_m3_avg: number | null
  o3_ug_m3_avg: number | null
}

export type OverviewTrends = {
  date_from: string
  date_to: string
  station_key: number | null
  points: TrendPoint[]
}

function qs(params: Record<string, string | number | undefined | null>) {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export function fetchOverviewMeta() {
  return apiGet<OverviewMeta>('/api/overview/meta')
}

export function fetchOverviewKpis(opts: {
  date_from?: string
  date_to?: string
  station_key?: number | null
}) {
  return apiGet<OverviewKpis>(
    `/api/overview/kpis${qs({
      date_from: opts.date_from,
      date_to: opts.date_to,
      station_key: opts.station_key ?? undefined,
    })}`,
  )
}

export function fetchOverviewTrends(opts: {
  date_from?: string
  date_to?: string
  station_key?: number | null
}) {
  return apiGet<OverviewTrends>(
    `/api/overview/trends${qs({
      date_from: opts.date_from,
      date_to: opts.date_to,
      station_key: opts.station_key ?? undefined,
    })}`,
  )
}
