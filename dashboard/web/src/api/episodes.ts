import { apiGet } from './client'

export type EpisodeSummaryRow = {
  station_key: number
  station_name: string
  episode_count: number
  duration_hours_avg: number | null
  duration_hours_sum: number
  pm25_mean_avg: number | null
  pm25_max_max: number | null
}

export type EpisodeRow = {
  episode_id: number
  station_key: number
  station_name: string
  start_time: string
  end_time: string
  duration_hours: number
  pm25_mean: number | null
  pm25_max: number | null
  year: number | null
  season: string | null
  temperature_c_avg: number | null
  relative_humidity_pct_avg: number | null
  wind_speed_m_s_avg: number | null
  rain_mm_sum: number | null
  cloud_cover_pct_avg: number | null
  threshold_ug_m3: number | null
  min_hours: number | null
}

export type MultiStationEventRow = {
  event_id: number
  start_time: string
  end_time: string
  duration_hours: number
  peak_station_count: number
  mean_station_count: number | null
  multi_station_k: number
}

export type EpisodesResponse = {
  date_from: string
  date_to: string
  station_key: number | null
  summary: EpisodeSummaryRow[]
  episodes: EpisodeRow[]
  multi_station_events: MultiStationEventRow[]
}

export function fetchEpisodes(opts: {
  date_from?: string
  date_to?: string
  station_key?: number | null
}) {
  const sp = new URLSearchParams()
  if (opts.date_from) sp.set('date_from', opts.date_from)
  if (opts.date_to) sp.set('date_to', opts.date_to)
  if (opts.station_key != null) sp.set('station_key', String(opts.station_key))
  const q = sp.toString()
  return apiGet<EpisodesResponse>(`/api/episodes${q ? `?${q}` : ''}`)
}
