import { createTheme, type MantineColorsTuple } from '@mantine/core'

// Design tokens for the whole dashboard. Components reference these roles, never raw hex.
// Series / status / sequential values follow the validated data-viz reference palette
// (fixed categorical order, CVD-checked); neutrals are a cool slate ramp.

export const FONT_FAMILY =
  'Inter, "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif'

const brand: MantineColorsTuple = [
  '#eef5fd',
  '#cde2fb',
  '#9ec5f4',
  '#6da7ec',
  '#3987e5',
  '#2a78d6',
  '#256abf',
  '#1c5cab',
  '#184f95',
  '#104281',
]

// Same lightness positions as Mantine's default gray, shifted to slate.
const gray: MantineColorsTuple = [
  '#f8fafc',
  '#f1f5f9',
  '#e9eef4',
  '#e2e8f0',
  '#cbd5e1',
  '#94a3b8',
  '#64748b',
  '#475569',
  '#334155',
  '#1e293b',
]

export const INK = {
  primary: '#0f172a',
  secondary: '#475569',
  muted: '#64748b',
  axis: '#cbd5e1',
  grid: '#e9eef4',
  border: '#e2e8f0',
  surface: '#ffffff',
  page: '#f6f8fb',
}

/** Categorical slots, assigned in this order (identity of a series). */
export const SERIES = {
  blue: '#2a78d6',
  orange: '#eb6834',
  aqua: '#1baf7a',
  yellow: '#eda100',
  magenta: '#e87ba4',
  green: '#008300',
  violet: '#6250d6',
  red: '#e34948',
}
export const SERIES_ORDER = Object.values(SERIES)

/** Reference / baseline series that should recede behind the main one. */
export const NEUTRAL_SERIES = { strong: '#334155', soft: '#94a3b8' }

/** Reserved status colours (e.g. alert outcomes); always shown together with a text label. */
export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
}

// PM2.5 bands, AQI-style. Validated as adjacent pairs (validate_palette.js): CVD ΔE ≥ 13.1,
// normal-vision ΔE ≥ 15.2. Yellow is lighter than the categorical band, so every use pairs
// the colour with its text label (badges, legends, popups) — never colour alone.
const LEVEL = {
  low: '#0ca30c',
  moderate: '#f2c200',
  elevated: '#ee7b22',
  high: '#d03b3b',
  veryHigh: '#7e3fa8',
}

export const CLUSTER = {
  elevated_core: { label: 'Nhóm A · ô nhiễm nặng', color: SERIES.orange },
  cleaner_outskirts: { label: 'Nhóm B · ô nhiễm nhẹ hơn', color: SERIES.aqua },
} as const

export function clusterInfo(label: string | null | undefined) {
  if (label && label in CLUSTER) return CLUSTER[label as keyof typeof CLUSTER]
  return { label: label ?? '—', color: NEUTRAL_SERIES.soft }
}

export type Pm25Level = { key: string; label: string; color: string }

/** PM2.5 (µg/m³) bands used across the dashboard; 115 is the alert threshold. */
export function pm25Level(value: number | null | undefined): Pm25Level {
  if (value == null) return { key: 'none', label: 'Chưa có số', color: NEUTRAL_SERIES.soft }
  if (value <= 35) return { key: 'low', label: 'Thấp', color: LEVEL.low }
  if (value <= 75) return { key: 'moderate', label: 'Trung bình', color: LEVEL.moderate }
  if (value <= 115) return { key: 'elevated', label: 'Hơi cao', color: LEVEL.elevated }
  if (value <= 150) return { key: 'high', label: 'Cao', color: LEVEL.high }
  return { key: 'very-high', label: 'Rất cao', color: LEVEL.veryHigh }
}

export const PM25_LEVELS: { range: string; level: Pm25Level }[] = [
  { range: '≤ 35', level: pm25Level(0) },
  { range: '35–75', level: pm25Level(50) },
  { range: '75–115', level: pm25Level(100) },
  { range: '115–150', level: pm25Level(120) },
  { range: '> 150', level: pm25Level(200) },
]

export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: 6,
  colors: { brand, gray },
  black: INK.primary,
  fontFamily: FONT_FAMILY,
  headings: {
    fontFamily: FONT_FAMILY,
    fontWeight: '650',
    sizes: {
      h1: { fontSize: '1.5rem', lineHeight: '1.25' },
      h2: { fontSize: '1rem', lineHeight: '1.4' },
      h3: { fontSize: '0.9375rem', lineHeight: '1.4' },
    },
  },
  defaultRadius: 'md',
  cursorType: 'pointer',
  focusRing: 'auto',
  respectReducedMotion: true,
  shadows: {
    xs: '0 1px 2px rgba(15, 23, 42, 0.04)',
    sm: '0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04)',
  },
  components: {
    Paper: { defaultProps: { radius: 'md', shadow: 'xs' } },
    Badge: {
      defaultProps: { radius: 'sm', variant: 'light' },
      styles: { root: { textTransform: 'none', letterSpacing: 0, fontWeight: 600 } },
    },
    Button: { defaultProps: { radius: 'md' }, styles: { root: { fontWeight: 500 } } },
    Table: {
      defaultProps: { verticalSpacing: 8, horizontalSpacing: 'md', fz: 'sm' },
    },
    Alert: { defaultProps: { radius: 'md', variant: 'light' } },
    Select: { defaultProps: { radius: 'md', comboboxProps: { shadow: 'md' } } },
    MultiSelect: { defaultProps: { radius: 'md', comboboxProps: { shadow: 'md' } } },
    TextInput: { defaultProps: { radius: 'md' } },
    SegmentedControl: { defaultProps: { radius: 'md' } },
    NavLink: { styles: { root: { borderRadius: 'var(--mantine-radius-md)' } } },
    Tooltip: { defaultProps: { withArrow: true } },
  },
})
