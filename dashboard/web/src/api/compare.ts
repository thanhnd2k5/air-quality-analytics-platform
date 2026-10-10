import { apiGet } from './client'

export type StationCompareRow = {
  station_key: number
  station_name: string
  district: string | null
  cluster_id: number | null
  cluster_label: string | null
  pm25_avg: number | null
  pm10_avg: number | null
  o3_avg: number | null
  day_count: number
  rank_pm25: number
}

export type StationCompareResponse = {
  date_from: string
  date_to: string
  rows: StationCompareRow[]
}

export function fetchStationCompare(opts: {
  date_from?: string
  date_to?: string
}) {
  const sp = new URLSearchParams()
  if (opts.date_from) sp.set('date_from', opts.date_from)
  if (opts.date_to) sp.set('date_to', opts.date_to)
  const q = sp.toString()
  return apiGet<StationCompareResponse>(
    `/api/stations/compare${q ? `?${q}` : ''}`,
  )
}
