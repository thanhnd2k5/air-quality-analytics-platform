import { apiGet } from './client'

export type WeatherSeriesPoint = {
  date_day: string
  pm25_ug_m3_avg: number | null
  temperature_c_avg: number | null
  relative_humidity_pct_avg: number | null
  wind_speed_m_s_avg: number | null
  rain_mm_sum: number | null
  cloud_cover_pct_avg: number | null
  pressure_hpa_avg: number | null
  dew_point_c_avg: number | null
}

export type WeatherScatterPoint = {
  date_day: string
  pm25_ug_m3_avg: number | null
  weather_value: number | null
}

export type WindRosePoint = {
  direction: string
  azimuth_deg: number
  hours: number
  exceed_pct: number | null
  pm25_avg: number | null
}

export type WeatherResponse = {
  date_from: string
  date_to: string
  station_key: number | null
  series: WeatherSeriesPoint[]
  scatter_variable: string
  scatter: WeatherScatterPoint[]
}

export type WindRoseResponse = {
  date_from: string
  date_to: string
  station_key: number | null
  points: WindRosePoint[]
}

export type ScatterVariable =
  | 'temperature_c_avg'
  | 'relative_humidity_pct_avg'
  | 'wind_speed_m_s_avg'
  | 'rain_mm_sum'
  | 'cloud_cover_pct_avg'
  | 'pressure_hpa_avg'
  | 'dew_point_c_avg'

export function fetchWeather(opts: {
  date_from?: string
  date_to?: string
  station_key?: number | null
  scatter_variable?: ScatterVariable
}) {
  const sp = new URLSearchParams()
  if (opts.date_from) sp.set('date_from', opts.date_from)
  if (opts.date_to) sp.set('date_to', opts.date_to)
  if (opts.station_key != null) sp.set('station_key', String(opts.station_key))
  if (opts.scatter_variable) sp.set('scatter_variable', opts.scatter_variable)
  const q = sp.toString()
  return apiGet<WeatherResponse>(`/api/weather${q ? `?${q}` : ''}`)
}

export function fetchWindRose(opts: { date_from?: string; date_to?: string; station_key?: number | null }) {
  const sp = new URLSearchParams()
  if (opts.date_from) sp.set('date_from', opts.date_from)
  if (opts.date_to) sp.set('date_to', opts.date_to)
  if (opts.station_key != null) sp.set('station_key', String(opts.station_key))
  const q = sp.toString()
  return apiGet<WindRoseResponse>(`/api/weather/wind-rose${q ? `?${q}` : ''}`)
}
