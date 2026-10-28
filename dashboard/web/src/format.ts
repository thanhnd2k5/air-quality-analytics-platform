// One number style for the whole app, the Vietnamese one used in the report: 1.234,5
// (thousands ".", decimals ","). Mixing it with toFixed()'s "105.0" makes "1.080" ambiguous.

const fixed = new Map<number, Intl.NumberFormat>()
const axis = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 3 })

function fixedFormat(digits: number) {
  let f = fixed.get(digits)
  if (!f) {
    f = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    fixed.set(digits, f)
  }
  return f
}

/** 1891.94 → "1.891,9"; null / NaN → "—". */
export function fmtNum(v: number | null | undefined, digits = 1): string {
  return v == null || !Number.isFinite(v) ? '—' : fixedFormat(digits).format(v)
}

/** A value already in percent: 12.34 → "12,3%". */
export function fmtPct(v: number | null | undefined, digits = 1): string {
  return v == null || !Number.isFinite(v) ? '—' : `${fixedFormat(digits).format(v)}%`
}

/** Signed, with a real minus sign: "+1,2" / "−0,4". */
export function fmtSigned(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v >= 0 ? '+' : '−'}${fixedFormat(digits).format(Math.abs(v))}`
}

/** Axis ticks: no forced decimals ("0,25", "1.000"). */
export function fmtAxis(v: number): string {
  return axis.format(v)
}
