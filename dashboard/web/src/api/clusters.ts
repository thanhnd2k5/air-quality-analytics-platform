import { apiGet } from './client'

export type ClusterStation = {
  station_key: number
  station_name: string
  district: string | null
}

export type ClusterGroup = {
  cluster_id: number
  cluster_label: string
  label_vi: string
  n_stations: number
  pm25_avg: number | null
  no2_avg: number | null
  co_avg: number | null
  stations: ClusterStation[]
}

export type KSelectionPoint = {
  method: string
  k: number
  silhouette: number
  inertia: number | null
}

export type ClustersResponse = {
  method: string
  k: number
  silhouette: number
  window_from: string
  window_to: string
  k_grid: KSelectionPoint[]
  groups: ClusterGroup[]
}

export function fetchClusters() {
  return apiGet<ClustersResponse>('/api/clusters')
}
