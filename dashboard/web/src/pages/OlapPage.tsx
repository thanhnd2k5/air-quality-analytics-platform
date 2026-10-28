import {
  ActionIcon,
  Badge,
  Button,
  CloseButton,
  Divider,
  Group,
  Menu,
  MultiSelect,
  Paper,
  Popover,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Tooltip,
  UnstyledButton,
  type ComboboxData,
} from '@mantine/core'
import {
  IconArrowDown,
  IconArrowUp,
  IconArrowsLeftRight,
  IconChevronDown,
  IconDatabase,
  IconFilterOff,
  IconLayoutGrid,
  IconPlus,
} from '@tabler/icons-react'
import {
  cloneElement,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from 'react'
import { fetchOlapMeta, fetchOlapQuery, type OlapMeta, type OlapResponse } from '../api/olap'
import { Chart } from '../components/Chart'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { Dot } from '../components/Pm25Badge'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { SERIES, pm25Level } from '../theme'

type Filters = Record<string, string[]>
type Axis = 'rows' | 'cols'

const SEASON_VI: Record<string, string> = {
  spring: 'Xuân',
  summer: 'Hạ',
  autumn: 'Thu',
  winter: 'Đông',
  night: 'Đêm',
  morning: 'Sáng',
  afternoon: 'Chiều',
  evening: 'Tối',
  northerly: 'Gió bắc',
  southerly: 'Gió nam',
  NE: 'Đông Bắc',
  SE: 'Đông Nam',
  SW: 'Tây Nam',
  NW: 'Tây Bắc',
}

// Dropdown groups: which dimension hierarchies (from /api/olap/meta) sit under which heading.
const ATTR_GROUPS: { label: string; hierarchies: string[] }[] = [
  { label: 'Thời gian', hierarchies: ['time', 'season'] },
  { label: 'Trong ngày', hierarchies: ['daytime'] },
  { label: 'Địa điểm', hierarchies: ['location'] },
  { label: 'Gió', hierarchies: ['wind'] },
]

const MEASURES = [
  { value: 'pm25_avg', label: 'PM2.5 TB' },
  { value: 'exceed_pct', label: '% giờ ≥ 115' },
  { value: 'exceed_hours', label: 'Số giờ ≥ 115' },
]

// Ready-made views for a live demo; the same ones the report screenshots use.
const EXAMPLES: { label: string; hint: string; rows: string; cols: string | null; measure: string; filters: Filters }[] = [
  {
    label: 'Năm × mùa',
    hint: 'Khối con tính trước; điểm bắt đầu để roll-up, drill-down',
    rows: 'year',
    cols: 'season',
    measure: 'pm25_avg',
    filters: {},
  },
  {
    label: 'Slice: mùa đông theo giờ',
    hint: 'Mùa = Đông, PM2.5 trung bình theo giờ trong ngày',
    rows: 'hour',
    cols: null,
    measure: 'pm25_avg',
    filters: { season: ['winter'] },
  },
  {
    label: 'Dice: 2 quận × tháng năm 2016',
    hint: 'Quận ∈ {Dongcheng, Xicheng} × Năm 2016, % giờ ≥ 115',
    rows: 'station',
    cols: 'month',
    measure: 'exceed_pct',
    filters: { district: ['Dongcheng', 'Xicheng'], year: ['2016'] },
  },
  {
    label: 'Hướng gió × mùa',
    hint: '% giờ PM2.5 ≥ 115 theo phần tư hướng gió',
    rows: 'wind_quadrant',
    cols: 'season',
    measure: 'exceed_pct',
    filters: {},
  },
]

function memberLabel(v: string) {
  return SEASON_VI[v] ?? v
}

function fmtValue(v: number | null | undefined, measure: string) {
  if (v === null || v === undefined) return '—'
  if (measure === 'hours' || measure === 'exceed_hours') return Math.round(v).toLocaleString('vi-VN')
  if (measure === 'exceed_pct') return `${v.toFixed(1)}%`
  return v.toFixed(1)
}

const UNIT: Record<string, string> = { pm25_avg: 'µg/m³', exceed_hours: 'giờ', hours: 'giờ' }

function fmtWithUnit(v: number | null | undefined, measure: string) {
  const text = fmtValue(v, measure)
  return v != null && UNIT[measure] ? `${text} ${UNIT[measure]}` : text
}

/** "PM2.5 trung bình (µg/m³)" → "PM2.5 trung bình" (the unit is shown next to the value). */
function measureName(label: string) {
  return label.replace(/\s*\([^)]*\)\s*$/, '')
}

type BodyProps = {
  onMouseOver?: (event: MouseEvent<HTMLElement>) => void
  onMouseLeave?: (event: MouseEvent<HTMLElement>) => void
}

/**
 * One floating tooltip for a whole table body. Cells only carry data-* attributes and the
 * hovered cell lives in this component's state, so moving across cells re-renders the
 * tooltip alone, never the table or the page.
 */
function CellTooltip({
  children,
  describe,
}: {
  children: ReactElement<BodyProps>
  describe: (cell: HTMLElement) => ReactNode
}) {
  const [hover, setHover] = useState<{ cell: Element | null; label: ReactNode }>({ cell: null, label: null })
  const body = cloneElement(children, {
    onMouseOver: (event: MouseEvent<HTMLElement>) => {
      const cell = (event.target as HTMLElement).closest<HTMLElement>('[data-cell]')
      // Same cell as before → return the previous state, so React skips the render.
      setHover((prev) => (prev.cell === cell ? prev : { cell, label: cell ? describe(cell) : null }))
    },
    onMouseLeave: () => setHover({ cell: null, label: null }),
  })
  return (
    <Tooltip.Floating
      label={hover.label}
      disabled={!hover.label}
      position="right-start"
      offset={18}
      color="white"
      styles={{
        tooltip: {
          color: 'var(--mantine-color-black)',
          border: '1px solid var(--mantine-color-gray-3)',
          boxShadow: '0 6px 20px rgba(15, 23, 42, 0.08)',
          padding: '8px 12px',
        },
      }}
    >
      {body}
    </Tooltip.Floating>
  )
}

// Optional deep link for demo scripts, e.g. /olap?rows=station&cols=month&filter=district:Dongcheng,Xicheng
function initialState() {
  const sp = new URLSearchParams(window.location.search)
  const filters: Filters = {}
  for (const f of sp.getAll('filter')) {
    const [attr, values] = f.split(':', 2)
    if (attr && values) filters[attr] = values.split(',').filter(Boolean)
  }
  return {
    rows: sp.get('rows') ?? 'year',
    cols: sp.has('cols') ? sp.get('cols') || null : 'season',
    measure: sp.get('measure') ?? 'pm25_avg',
    filters,
  }
}

type AxisControlProps = {
  label: string
  value: string | null
  options: ComboboxData
  onChange: (value: string | null) => void
  clearable?: boolean
  /** Levels of the selected attribute's hierarchy, top → bottom. */
  path: { name: string; label: string; blocked: boolean }[]
  up: string | null
  down: string | null
  onMove: (target: string) => void
}

/** Attribute picker with roll-up / drill-down beside it and the hierarchy path below. */
function AxisControl({ label, value, options, onChange, clearable, path, up, down, onMove }: AxisControlProps) {
  const labelOf = (name: string | null) => path.find((p) => p.name === name)?.label ?? ''
  const step = (target: string | null, kind: 'Roll-up' | 'Drill-down', icon: ReactNode) => {
    const text = target
      ? `${kind}: ${kind === 'Roll-up' ? 'lên' : 'xuống'} ${labelOf(target)}`
      : kind === 'Roll-up'
        ? 'Đã ở mức cao nhất'
        : 'Đã ở mức chi tiết nhất'
    return (
      <Tooltip label={text}>
        <ActionIcon
          variant="default"
          size={36}
          aria-label={text}
          aria-disabled={!target || undefined}
          data-disabled={!target || undefined}
          onClick={() => target && onMove(target)}
        >
          {icon}
        </ActionIcon>
      </Tooltip>
    )
  }
  return (
    <Stack gap={6}>
      <Text size="sm" fw={500}>
        {label}
      </Text>
      <Group gap={6} wrap="nowrap">
        <Select
          aria-label={label}
          data={options}
          value={value}
          onChange={onChange}
          clearable={clearable}
          allowDeselect={false}
          placeholder="(không)"
          maxDropdownHeight={480}
          w={170}
        />
        {value && step(up, 'Roll-up', <IconArrowUp size={16} />)}
        {value && step(down, 'Drill-down', <IconArrowDown size={16} />)}
      </Group>
      <Group gap={4} wrap="wrap" mih={20}>
        {value && path.length > 1 ? (
          path.map((level, i) => (
            <Group key={level.name} gap={4} wrap="nowrap">
              {i > 0 && (
                <Text size="xs" c="gray.5" aria-hidden>
                  ›
                </Text>
              )}
              {level.name === value ? (
                <Text size="xs" fw={650} c="brand.7">
                  {level.label}
                </Text>
              ) : (
                <UnstyledButton
                  onClick={() => onMove(level.name)}
                  disabled={level.blocked}
                  title={level.blocked ? 'Đang dùng ở trục còn lại' : `Chuyển tới mức ${level.label}`}
                >
                  <Text size="xs" c={level.blocked ? 'gray.4' : 'dimmed'} td={level.blocked ? undefined : 'underline'}>
                    {level.label}
                  </Text>
                </UnstyledButton>
              )}
            </Group>
          ))
        ) : (
          <Text size="xs" c="dimmed">
            {value ? 'Không có phân cấp' : 'Chỉ xem theo hàng'}
          </Text>
        )}
      </Group>
    </Stack>
  )
}

export function OlapPage() {
  const [init] = useState(initialState)
  const [meta, setMeta] = useState<OlapMeta | null>(null)
  const [rows, setRows] = useState(init.rows)
  const [cols, setCols] = useState<string | null>(init.cols)
  const [measure, setMeasure] = useState(init.measure)
  const [filters, setFilters] = useState<Filters>(init.filters)
  const [lastOp, setLastOp] = useState('Khối ban đầu')
  // Table (already heat-shaded) by default; the chart is the same numbers, for big cubes.
  const [view, setView] = useState<'table' | 'chart'>('table')
  const [editor, setEditor] = useState<{ open: boolean; attr: string | null; values: string[] }>({
    open: false,
    attr: null,
    values: [],
  })
  const [data, setData] = useState<OlapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchOlapMeta()
      .then(setMeta)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchOlapQuery({ rows, cols, measure, filters })
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [rows, cols, measure, filters])

  // Keep the URL in step with the view, so any state can be reopened or shared as a link.
  useEffect(() => {
    const sp = new URLSearchParams({ rows, cols: cols ?? '', measure })
    for (const [attr, values] of Object.entries(filters)) {
      if (values.length) sp.append('filter', `${attr}:${values.join(',')}`)
    }
    window.history.replaceState(window.history.state, '', `${window.location.pathname}?${sp}`)
  }, [rows, cols, measure, filters])

  const attrs = useMemo(() => meta?.attributes ?? [], [meta])
  const attrLabel = useCallback(
    (name: string | null) => attrs.find((a) => a.name === name)?.label ?? name ?? '',
    [attrs],
  )
  const chainOf = (attr: string | null): string[] => {
    const a = attrs.find((x) => x.name === attr)
    if (!a || !meta) return []
    return meta.hierarchies[a.hierarchy] ?? [a.name]
  }
  const current = (axis: Axis) => (axis === 'rows' ? rows : cols)
  const other = (axis: Axis) => (axis === 'rows' ? cols : rows)
  const step = (axis: Axis, delta: -1 | 1): string | null => {
    const attr = current(axis)
    const chain = chainOf(attr)
    const next = chain[chain.indexOf(attr ?? '') + delta]
    return next && next !== other(axis) ? next : null
  }
  const setAxis = (axis: Axis, value: string | null) => {
    if (axis === 'rows') {
      if (value) setRows(value)
    } else {
      setCols(value)
    }
  }

  /** Roll-up or drill-down along the attribute's own hierarchy (one or several levels). */
  const moveTo = (axis: Axis, target: string) => {
    const from = current(axis)
    if (!from || target === from || target === other(axis)) return
    const chain = chainOf(from)
    const kind = chain.indexOf(target) < chain.indexOf(from) ? 'Roll-up' : 'Drill-down'
    setLastOp(`${kind} ${axis === 'rows' ? 'hàng' : 'cột'}: ${attrLabel(from)} → ${attrLabel(target)}`)
    setAxis(axis, target)
  }

  /** Drill-down into one member: keep only that member, then go one level deeper. */
  const drillInto = (axis: Axis, member: string) => {
    const from = current(axis)
    const child = step(axis, 1)
    if (!from || !child) return
    setFilters((f) => ({ ...f, [from]: [member] }))
    setLastOp(`Drill-down vào ${attrLabel(from)} = ${memberLabel(member)} → ${attrLabel(child)}`)
    setAxis(axis, child)
  }

  const pivot = () => {
    if (!cols) return
    setLastOp(`Pivot: ${attrLabel(cols)} lên hàng, ${attrLabel(rows)} sang cột`)
    setRows(cols)
    setCols(rows)
  }

  const describeFilters = (next: Filters) => {
    const entries = Object.entries(next)
    if (!entries.length) return 'Bỏ mọi bộ lọc'
    if (entries.length === 1 && entries[0][1].length === 1)
      return `Slice: ${attrLabel(entries[0][0])} = ${memberLabel(entries[0][1][0])}`
    return 'Dice: ' + entries.map(([a, v]) => `${attrLabel(a)} ∈ {${v.map(memberLabel).join(', ')}}`).join(' × ')
  }

  const setFilterValues = (attr: string, values: string[]) => {
    const next = { ...filters }
    if (values.length) next[attr] = values
    else delete next[attr]
    setFilters(next)
    setLastOp(describeFilters(next))
  }

  const openEditor = (attr: string | null) =>
    setEditor({ open: true, attr, values: attr ? (filters[attr] ?? []) : [] })

  const applyExample = (ex: (typeof EXAMPLES)[number]) => {
    setRows(ex.rows)
    setCols(ex.cols)
    setMeasure(ex.measure)
    setFilters(ex.filters)
    setLastOp(`Mẫu: ${ex.label}`)
  }

  const cellMap = useMemo(() => {
    const m = new Map<string, number | null>()
    for (const c of data?.cells ?? []) m.set(`${c.row}\u0000${c.col}`, c.value)
    return m
  }, [data])

  const [vmin, vmax] = useMemo(() => {
    const vals = (data?.cells ?? []).map((c) => c.value).filter((v): v is number => v != null)
    return vals.length ? [Math.min(...vals), Math.max(...vals)] : [0, 1]
  }, [data])

  // One-hue orange shading on the table cells, kept light enough for dark text on top.
  const heat = (v: number | null | undefined) => {
    if (v == null || vmax === vmin) return undefined
    const t = (v - vmin) / (vmax - vmin)
    return `rgba(235, 104, 52, ${0.06 + 0.42 * t})`
  }

  // A 2-D result is read from the shaded table; only a 1-D result (no column) gets a bar chart.
  const showChart = view === 'chart' && data != null && !data.cols
  const chartOption = useMemo(() => {
    if (!data || data.cols || !showChart) return null
    return {
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: number | null) => fmtWithUnit(v, data.measure),
      },
      grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
      xAxis: { type: 'category', data: data.row_members.map(memberLabel) },
      yAxis: { type: 'value', name: data.measure_label },
      series: [
        {
          type: 'bar',
          name: data.measure_label,
          data: data.row_members.map((r) => data.row_totals[r]),
          color: SERIES.blue,
        },
      ],
    }
  }, [data, showChart])

  // Tooltip body for a hovered cell (data-row / data-col absent = total over all members):
  // where it sits, its value with unit, and the PM2.5 band.
  const describeCell = (cell: HTMLElement): ReactNode => {
    if (!data) return null
    const row = cell.dataset.row ?? null
    const col = cell.dataset.col ?? null
    const value =
      row != null && col != null
        ? cellMap.get(`${row}\u0000${col}`)
        : row != null
          ? data.row_totals[row]
          : col != null
            ? data.col_totals[col]
            : data.grand_total
    const part = (attr: string | null, member: string | null) =>
      member == null ? `mọi ${attrLabel(attr).toLowerCase()}` : `${attrLabel(attr)} ${memberLabel(member)}`
    const scope =
      row == null && col == null
        ? 'Tổng chung'
        : data.cols
          ? `${part(data.rows, row)} · ${part(data.cols, col)}`
          : part(data.rows, row)
    const level = pm25Level(value)
    return (
      <Stack gap={4} maw={280}>
        <Text size="xs" fw={650}>
          {scope.charAt(0).toUpperCase() + scope.slice(1)}
        </Text>
        {value == null ? (
          <Text size="xs" c="dimmed">
            Không có giờ quan trắc nào thuộc tổ hợp này.
          </Text>
        ) : (
          <Text size="xs">
            {measureName(data.measure_label)}: <b className="tabular">{fmtWithUnit(value, data.measure)}</b>
          </Text>
        )}
        {data.measure === 'pm25_avg' && value != null && (
          <Group gap={6} wrap="nowrap">
            <Dot color={level.color} />
            <Text size="xs">Mức {level.label.toLowerCase()}</Text>
          </Group>
        )}
        {Object.keys(filters).length > 0 && (
          <Text size="xs" c="dimmed">
            Trong phạm vi bộ lọc đang bật
          </Text>
        )}
      </Stack>
    )
  }

  // Dropdown options grouped by dimension; inside a group, coarse → fine (the roll-up order).
  const attrOptions = (exclude?: string | null): ComboboxData => {
    const grouped = ATTR_GROUPS.map((g) => ({
      group: g.label,
      items: g.hierarchies
        .flatMap((h) => meta?.hierarchies[h] ?? [])
        .filter((name) => name !== exclude && attrs.some((a) => a.name === name))
        .map((name) => ({ value: name, label: attrLabel(name) })),
    }))
    const placed = new Set(grouped.flatMap((g) => g.items.map((i) => i.value)))
    const rest = attrs
      .filter((a) => !placed.has(a.name) && a.name !== exclude)
      .map((a) => ({ value: a.name, label: a.label }))
    return [...grouped, { group: 'Khác', items: rest }].filter((g) => g.items.length > 0)
  }
  const pathFor = (axis: Axis) =>
    chainOf(current(axis)).map((name) => ({ name, label: attrLabel(name), blocked: name === other(axis) }))
  const rowChild = data ? step('rows', 1) : null
  const colChild = data?.cols ? step('cols', 1) : null
  const editorMembers = (attrs.find((a) => a.name === editor.attr)?.members ?? []).map((m) => ({
    value: m,
    label: memberLabel(m),
  }))

  return (
    <Stack gap="lg">
      <PageHeader
        title="Phân tích OLAP"
        description="PM2.5 theo thời gian, địa điểm và hướng gió: roll-up, drill-down, slice, dice và pivot trên lược đồ sao."
      />

      <Paper withBorder p="lg">
        <Stack gap="md">
          <Group align="flex-start" gap="lg" wrap="wrap">
            <AxisControl
              label="Hàng"
              value={rows}
              options={attrOptions(cols)}
              onChange={(v) => v && setRows(v)}
              path={pathFor('rows')}
              up={step('rows', -1)}
              down={step('rows', 1)}
              onMove={(t) => moveTo('rows', t)}
            />
            <Stack gap={6}>
              <Text size="sm" fw={500} aria-hidden>
                {' '}
              </Text>
              <Tooltip label={cols ? 'Pivot: đổi hàng ↔ cột' : 'Chọn một cột để pivot'}>
                <ActionIcon
                  variant="default"
                  size={36}
                  aria-label="Pivot: đổi hàng và cột"
                  aria-disabled={!cols || undefined}
                  data-disabled={!cols || undefined}
                  onClick={pivot}
                >
                  <IconArrowsLeftRight size={16} />
                </ActionIcon>
              </Tooltip>
            </Stack>
            <AxisControl
              label="Cột"
              value={cols}
              options={attrOptions(rows)}
              onChange={setCols}
              clearable
              path={pathFor('cols')}
              up={step('cols', -1)}
              down={step('cols', 1)}
              onMove={(t) => moveTo('cols', t)}
            />
            <Stack gap={6}>
              <Text size="sm" fw={500}>
                Độ đo
              </Text>
              <SegmentedControl value={measure} onChange={setMeasure} data={MEASURES} />
            </Stack>
          </Group>

          <Divider color="gray.2" />

          <Group gap="xs" wrap="wrap" justify="space-between">
            <Group gap="xs" wrap="wrap">
              <Text size="sm" fw={500} mr={4}>
                Lọc
              </Text>
              {Object.entries(filters).map(([attr, values]) => (
                <Badge
                  key={attr}
                  color="brand"
                  size="lg"
                  rightSection={
                    <CloseButton
                      size="xs"
                      aria-label={`Bỏ lọc ${attrLabel(attr)}`}
                      onClick={() => setFilterValues(attr, [])}
                    />
                  }
                >
                  <UnstyledButton
                    onClick={() => openEditor(attr)}
                    title="Sửa bộ lọc"
                    fz="inherit"
                    fw="inherit"
                    c="inherit"
                  >
                    {attrLabel(attr)}: {values.map(memberLabel).join(', ')}
                  </UnstyledButton>
                </Badge>
              ))}
              <Popover
                opened={editor.open}
                onChange={(open) => setEditor((s) => ({ ...s, open }))}
                position="bottom-start"
                shadow="md"
                trapFocus
                width={320}
              >
                <Popover.Target>
                  <Button
                    variant="default"
                    size="xs"
                    leftSection={<IconPlus size={14} />}
                    onClick={() => (editor.open ? setEditor((s) => ({ ...s, open: false })) : openEditor(null))}
                  >
                    Thêm bộ lọc
                  </Button>
                </Popover.Target>
                <Popover.Dropdown>
                  <Stack gap="sm">
                    <Select
                      label="Thuộc tính"
                      placeholder="Chọn thuộc tính"
                      maxDropdownHeight={480}
                      data={attrOptions()}
                      value={editor.attr}
                      onChange={(attr) => setEditor({ open: true, attr, values: attr ? (filters[attr] ?? []) : [] })}
                      comboboxProps={{ withinPortal: false }}
                    />
                    {editor.attr && (
                      <MultiSelect
                        label="Giữ lại các giá trị"
                        placeholder="Chọn một (slice) hoặc nhiều (dice)"
                        searchable
                        data={editorMembers}
                        value={editor.values}
                        onChange={(values) => setEditor((s) => ({ ...s, values }))}
                        comboboxProps={{ withinPortal: false }}
                        maxDropdownHeight={220}
                      />
                    )}
                    <Group justify="flex-end" gap="xs">
                      <Button size="xs" variant="default" onClick={() => setEditor((s) => ({ ...s, open: false }))}>
                        Huỷ
                      </Button>
                      <Button
                        size="xs"
                        disabled={!editor.attr}
                        onClick={() => {
                          if (editor.attr) setFilterValues(editor.attr, editor.values)
                          setEditor((s) => ({ ...s, open: false }))
                        }}
                      >
                        Áp dụng
                      </Button>
                    </Group>
                  </Stack>
                </Popover.Dropdown>
              </Popover>
              {Object.keys(filters).length > 0 && (
                <Button
                  variant="subtle"
                  color="gray"
                  size="xs"
                  leftSection={<IconFilterOff size={14} />}
                  onClick={() => {
                    setFilters({})
                    setLastOp('Bỏ mọi bộ lọc')
                  }}
                >
                  Xoá lọc
                </Button>
              )}
            </Group>

            <Menu position="bottom-end" shadow="md" width={300}>
              <Menu.Target>
                <Button variant="light" size="xs" leftSection={<IconLayoutGrid size={14} />}>
                  Mẫu nhanh
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                {EXAMPLES.map((ex) => (
                  <Menu.Item key={ex.label} onClick={() => applyExample(ex)}>
                    <Text size="sm" fw={500}>
                      {ex.label}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {ex.hint}
                    </Text>
                  </Menu.Item>
                ))}
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Stack>
      </Paper>

      {error && <ErrorAlert title="Không chạy được truy vấn OLAP" message={error} />}
      {!data && loading && !error && <LoadingBlock height={260} />}

      {data && !error && (
        <>
          <Panel
            title="Kết quả"
            description={`Mỗi ô: ${data.measure_label}.${
              !showChart && (rowChild || colChild)
                ? ' Nhấn tên một hàng hoặc một cột để drill-down vào đúng giá trị đó.'
                : ''
            }`}
            busy={loading}
            actions={
              !data.cols && (
                <SegmentedControl
                  size="xs"
                  value={view}
                  onChange={(v) => setView(v as 'table' | 'chart')}
                  data={[
                    { value: 'table', label: 'Bảng' },
                    { value: 'chart', label: 'Biểu đồ cột' },
                  ]}
                />
              )
            }
          >
            <Group gap={6} mb="sm" wrap="wrap">
              <Text size="xs" c="dimmed">
                Thao tác gần nhất:
              </Text>
              <Text size="sm" fw={600}>
                {lastOp}
              </Text>
            </Group>
            {showChart && chartOption ? (
              <Chart
                option={chartOption}
                height={300}
                label={`Biểu đồ cột ${measureName(data.measure_label)} theo ${attrLabel(data.rows)}.`}
              />
            ) : (
            <Table.ScrollContainer minWidth={480}>
              <Table withTableBorder withColumnBorders highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>
                      {attrLabel(data.rows)}
                      {data.cols ? ` \\ ${attrLabel(data.cols)}` : ''}
                    </Table.Th>
                    {data.cols ? (
                      data.col_members.map((c) => (
                        <Table.Th key={c} ta="right">
                          {colChild ? (
                            <UnstyledButton
                              onClick={() => drillInto('cols', c)}
                              title={`Drill-down vào ${memberLabel(c)} → ${attrLabel(colChild)}`}
                              fz="inherit"
                              fw="inherit"
                              c="inherit"
                            >
                              <Group gap={2} wrap="nowrap" justify="flex-end">
                                {memberLabel(c)}
                                <IconChevronDown size={12} />
                              </Group>
                            </UnstyledButton>
                          ) : (
                            memberLabel(c)
                          )}
                        </Table.Th>
                      ))
                    ) : (
                      <Table.Th ta="right">{data.measure_label}</Table.Th>
                    )}
                    {data.cols && <Table.Th ta="right">Tổng</Table.Th>}
                  </Table.Tr>
                </Table.Thead>
                <CellTooltip describe={describeCell}>
                <Table.Tbody>
                  {data.row_members.map((r) => (
                    <Table.Tr key={r}>
                      <Table.Td fw={600} style={{ whiteSpace: 'nowrap' }}>
                        {rowChild ? (
                          <UnstyledButton
                            onClick={() => drillInto('rows', r)}
                            title={`Drill-down vào ${memberLabel(r)} → ${attrLabel(rowChild)}`}
                            fw={600}
                            fz="sm"
                          >
                            <Group gap={4} wrap="nowrap">
                              {memberLabel(r)}
                              <IconChevronDown size={14} color="var(--mantine-color-dimmed)" />
                            </Group>
                          </UnstyledButton>
                        ) : (
                          memberLabel(r)
                        )}
                      </Table.Td>
                      {data.cols ? (
                        data.col_members.map((c) => {
                          const v = cellMap.get(`${r}\u0000${c}`)
                          return (
                            <Table.Td key={c} ta="right" style={{ background: heat(v) }} data-cell data-row={r} data-col={c}>
                              {fmtValue(v, data.measure)}
                            </Table.Td>
                          )
                        })
                      ) : (
                        <Table.Td ta="right" style={{ background: heat(data.row_totals[r]) }} data-cell data-row={r}>
                          {fmtValue(data.row_totals[r], data.measure)}
                        </Table.Td>
                      )}
                      {data.cols && (
                        <Table.Td ta="right" fw={600} data-cell data-row={r}>
                          {fmtValue(data.row_totals[r], data.measure)}
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                  <Table.Tr bg="gray.0">
                    <Table.Td fw={650}>Tổng</Table.Td>
                    {data.cols &&
                      data.col_members.map((c) => (
                        <Table.Td key={c} ta="right" fw={600} data-cell data-col={c}>
                          {fmtValue(data.col_totals[c], data.measure)}
                        </Table.Td>
                      ))}
                    <Table.Td ta="right" fw={650} data-cell>
                      {fmtValue(data.grand_total, data.measure)}
                    </Table.Td>
                  </Table.Tr>
                </Table.Tbody>
                </CellTooltip>
              </Table>
            </Table.ScrollContainer>
            )}
            <Group gap={6} mt="sm" wrap="nowrap" align="flex-start">
              <IconDatabase size={14} color="var(--mantine-color-dimmed)" style={{ flex: 'none', marginTop: 2 }} />
              <Text size="xs" c="dimmed">
                {data.source} · {data.elapsed_ms} ms
              </Text>
            </Group>
          </Panel>
        </>
      )}
    </Stack>
  )
}
