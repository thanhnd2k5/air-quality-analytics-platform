import { apiGet, apiGetFresh } from './client'

export type ColumnMissing = {
  column: string
  label: string
  kind: string
  missing_at_source: number
  filled: number
  remaining: number
  treatment: string
}

export type PipelineStep = { step: string; status: string; seconds: number | null; error: string | null }

export type PipelineRun = {
  ok: boolean
  finished_at: string | null
  total_seconds: number | null
  scope: string
  steps: PipelineStep[]
}

export type QualitySummary = {
  warehouse: {
    fact_rows: number
    distinct_keys: number
    stations: number
    first_hour: string | null
    last_hour: string | null
  }
  status_counts: { status: string; rows: number }[]
  sources: { source_system: string; rows: number }[]
  loads: { dataset: string; files: number; rows: number; last_loaded_at: string | null }[]
  columns: ColumnMissing[]
  reconcile: {
    ok: boolean
    errors: string[]
    datasets: { dataset: string; source_rows: number | null; target_rows: number | null; stations: number | null }[]
  } | null
  last_run: PipelineRun | null
  last_full_run: PipelineRun | null
  dbt_tests: { passed: number; errors: number; total: number; finished_at: string | null } | null
}

/** Cached like the other pages (the API caches it too, per data version); `fresh` skips the browser copy. */
export function fetchQualitySummary(fresh = false) {
  const path = '/api/quality/summary'
  return fresh ? apiGetFresh<QualitySummary>(path) : apiGet<QualitySummary>(path)
}

export type ServiceCheck = { name: string; role: string; ok: boolean; latency_ms: number; detail: string | null }

/** Live probe of PostgreSQL and MinIO; never cached, so each poll shows the state right now. */
export function fetchServices() {
  return apiGetFresh<{ checked_at: string; services: ServiceCheck[] }>('/api/health/services')
}
