import { apiGet } from './client'

export type MapStationPoint = {
  station_key: number
  station_name: string
  district: string | null
  latitude: number
  longitude: number
  coordinate_status: string | null
  cluster_id: number | null
  cluster_label: string | null
  pm25_ug_m3_avg: number | null
  date_day: string | null
}

export type MapSnapshotResponse = {
  date_day: string
  data_min: string
  data_max: string
  coordinate_note: string
  points: MapStationPoint[]
}

export function fetchMapSnapshot(date_day?: string) {
  const q = date_day ? `?date_day=${date_day}` : ''
  return apiGet<MapSnapshotResponse>(`/api/map/snapshot${q}`)
}
