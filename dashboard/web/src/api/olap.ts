import { apiGet } from './client'

export type OlapAttribute = {
  name: string
  label: string
  hierarchy: string
  members: string[]
}

export type OlapMeta = {
  attributes: OlapAttribute[]
  hierarchies: Record<string, string[]>
  measures: Record<string, string>
  cube_attributes: string[]
}

export type OlapCell = { row: string; col: string; value: number | null }

export type OlapResponse = {
  rows: string
  cols: string | null
  measure: string
  measure_label: string
  filters: Record<string, string[]>
  source: string
  cuboid: string | null
  sql: string
  elapsed_ms: number
  row_members: string[]
  col_members: string[]
  cells: OlapCell[]
  row_totals: Record<string, number | null>
  col_totals: Record<string, number | null>
  grand_total: number | null
}

export function fetchOlapMeta() {
  return apiGet<OlapMeta>('/api/olap/meta')
}

export function fetchOlapQuery(opts: {
  rows: string
  cols: string | null
  measure: string
  filters: Record<string, string[]>
}) {
  const sp = new URLSearchParams()
  sp.set('rows', opts.rows)
  if (opts.cols) sp.set('cols', opts.cols)
  sp.set('measure', opts.measure)
  for (const [attr, values] of Object.entries(opts.filters)) {
    if (values.length) sp.append('filter', `${attr}:${values.join(',')}`)
  }
  return apiGet<OlapResponse>(`/api/olap/query?${sp.toString()}`)
}
