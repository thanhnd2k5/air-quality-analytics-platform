import { apiGet } from './client'

export type Station = {
  station_key: number
  station_code: string | null
  station_name: string
  district: string | null
  latitude: number | null
  longitude: number | null
  coordinate_status: string | null
  cluster_id: number | null
  cluster_label: string | null
}

export function fetchStations(): Promise<Station[]> {
  return apiGet<Station[]>('/api/stations')
}
