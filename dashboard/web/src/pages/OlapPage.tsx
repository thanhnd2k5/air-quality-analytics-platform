import {
  Accordion,
  Alert,
  Badge,
  Button,
  Code,
  CloseButton,
  Group,
  Loader,
  MultiSelect,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import {
  IconArrowsExchange,
  IconChevronDown,
  IconChevronUp,
  IconDatabase,
  IconFilterOff,
} from '@tabler/icons-react'
import ReactECharts from 'echarts-for-react'
import { useEffect, useMemo, useState } from 'react'
import { fetchOlapMeta, fetchOlapQuery, type OlapMeta, type OlapResponse } from '../api/olap'

type Filters = Record<string, string[]>

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

function memberLabel(v: string) {
  return SEASON_VI[v] ?? v
}

function fmtValue(v: number | null | undefined, measure: string) {
  if (v === null || v === undefined) return '—'
  if (measure === 'hours') return Math.round(v).toLocaleString('vi-VN')
  if (measure === 'exceed_pct') return `${v.toFixed(1)}%`
  return v.toFixed(1)
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

export function OlapPage() {
  const [init] = useState(initialState)
  const [meta, setMeta] = useState<OlapMeta | null>(null)
  const [rows, setRows] = useState(init.rows)
  const [cols, setCols] = useState<string | null>(init.cols)
  const [measure, setMeasure] = useState(init.measure)
  const [filters, setFilters] = useState<Filters>(init.filters)
  const [filterAttr, setFilterAttr] = useState<string | null>(null)
  const [lastOp, setLastOp] = useState('Khối ban đầu')
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

  const attrs = useMemo(() => meta?.attributes ?? [], [meta])
  const attrLabel = (name: string | null) => attrs.find((a) => a.name === name)?.label ?? name ?? ''

  const level = (attr: string, delta: -1 | 1): string | null => {
    const a = attrs.find((x) => x.name === attr)
    if (!a || !meta) return null
    const chain = meta.hierarchies[a.hierarchy] ?? []
    const i = chain.indexOf(attr)
    const next = chain[i + delta]
    return next && next !== cols ? next : null
  }

  const rollUp = () => {
    const parent = level(rows, -1)
    if (!parent) return
    setLastOp(`Roll-up: ${attrLabel(rows)} → ${attrLabel(parent)}`)
    setRows(parent)
  }

  const drillDown = (member?: string) => {
    const child = level(rows, 1)
    if (!child) return
    if (member) {
      setFilters((f) => ({ ...f, [rows]: [member] }))
      setLastOp(`Drill-down vào ${attrLabel(rows)} = ${memberLabel(member)} → ${attrLabel(child)}`)
    } else {
      setLastOp(`Drill-down: ${attrLabel(rows)} → ${attrLabel(child)}`)
    }
    setRows(child)
  }

  const pivot = () => {
    if (!cols) return
    setLastOp(`Pivot: ${attrLabel(cols)} lên hàng, ${attrLabel(rows)} sang cột`)
    setRows(cols)
    setCols(rows)
  }

  const setFilterValues = (attr: string, values: string[]) => {
    const next = { ...filters }
    if (values.length) next[attr] = values
    else delete next[attr]
    setFilters(next)
    const entries = Object.entries(next)
    if (!entries.length) setLastOp('Bỏ mọi bộ lọc')
    else if (entries.length === 1 && entries[0][1].length === 1)
      setLastOp(`Slice: ${attrLabel(entries[0][0])} = ${memberLabel(entries[0][1][0])}`)
    else
      setLastOp(
        'Dice: ' + entries.map(([a, v]) => `${attrLabel(a)} ∈ {${v.map(memberLabel).join(', ')}}`).join(' × '),
      )
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

  const heat = (v: number | null | undefined) => {
    if (v == null || vmax === vmin) return undefined
    const t = (v - vmin) / (vmax - vmin)
    return `rgba(234, 88, 12, ${0.08 + 0.5 * t})`
  }

  const chartOption = useMemo(() => {
    if (!data) return null
    if (!data.cols) {
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: 56, right: 16, top: 24, bottom: 48 },
        xAxis: { type: 'category', data: data.row_members.map(memberLabel), axisLabel: { hideOverlap: true } },
        yAxis: { type: 'value', name: data.measure_label },
        series: [{ type: 'bar', data: data.row_members.map((r) => data.row_totals[r]), itemStyle: { color: '#ea580c' } }],
      }
    }
    return {
      tooltip: { position: 'top' },
      grid: { left: 110, right: 96, top: 16, bottom: 40 },
      xAxis: { type: 'category', data: data.col_members.map(memberLabel), splitArea: { show: true } },
      yAxis: { type: 'category', inverse: true, data: data.row_members.map(memberLabel), splitArea: { show: true } },
      visualMap: {
        min: vmin,
        max: vmax,
        calculable: true,
        orient: 'vertical',
        right: 0,
        top: 'center',
        precision: 1,
        inRange: { color: ['#fff7ed', '#fdba74', '#c2410c'] },
      },
      series: [
        {
          type: 'heatmap',
          data: data.cells.map((c) => [
            data.col_members.indexOf(c.col),
            data.row_members.indexOf(c.row),
            c.value == null ? null : Number(c.value.toFixed(1)),
          ]),
          label: { show: data.row_members.length * data.col_members.length <= 120 },
        },
      ],
    }
  }, [data, vmin, vmax])

  const attrOptions = attrs.map((a) => ({ value: a.name, label: a.label }))
  const parent = level(rows, -1)
  const child = level(rows, 1)

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Phân tích OLAP</Title>
        <Text size="sm" c="dimmed">
          PM2.5 theo thời gian, địa điểm và hướng gió.
        </Text>
      </div>

      <Paper withBorder p="md">
        <Group align="flex-end" gap="sm" wrap="wrap">
          <Select label="Hàng" data={attrOptions} value={rows} onChange={(v) => v && v !== cols && setRows(v)} w={190} />
          <Select
            label="Cột"
            clearable
            placeholder="(không)"
            data={attrOptions.filter((o) => o.value !== rows)}
            value={cols}
            onChange={setCols}
            w={190}
          />
          <div>
            <Text size="sm" fw={500} mb={4}>
              Độ đo
            </Text>
            <SegmentedControl
              value={measure}
              onChange={setMeasure}
              data={[
                { value: 'pm25_avg', label: 'PM2.5 TB' },
                { value: 'exceed_pct', label: '% giờ ≥115' },
                { value: 'hours', label: 'Số giờ' },
              ]}
            />
          </div>
        </Group>
        <Group mt="md" gap="xs">
          <Button variant="light" leftSection={<IconChevronUp size={16} />} disabled={!parent} onClick={rollUp}>
            Roll-up{parent ? ` → ${attrLabel(parent)}` : ''}
          </Button>
          <Button variant="light" leftSection={<IconChevronDown size={16} />} disabled={!child} onClick={() => drillDown()}>
            Drill-down{child ? ` → ${attrLabel(child)}` : ''}
          </Button>
          <Button variant="light" leftSection={<IconArrowsExchange size={16} />} disabled={!cols} onClick={pivot}>
            Pivot (đổi hàng ↔ cột)
          </Button>
          <Button
            variant="subtle"
            color="gray"
            leftSection={<IconFilterOff size={16} />}
            disabled={!Object.keys(filters).length}
            onClick={() => {
              setFilters({})
              setLastOp('Bỏ mọi bộ lọc')
            }}
          >
            Bỏ lọc
          </Button>
        </Group>
        <Group mt="md" align="flex-end" gap="sm" wrap="wrap">
          <Select
            label="Lọc theo"
            placeholder="Chọn thuộc tính"
            data={attrOptions}
            value={filterAttr}
            onChange={setFilterAttr}
            w={190}
          />
          {filterAttr && (
            <MultiSelect
              label={`Giá trị ${attrLabel(filterAttr)}`}
              searchable
              data={(attrs.find((a) => a.name === filterAttr)?.members ?? []).map((m) => ({
                value: m,
                label: memberLabel(m),
              }))}
              value={filters[filterAttr] ?? []}
              onChange={(v) => setFilterValues(filterAttr, v)}
              w={320}
            />
          )}
        </Group>
        {Object.keys(filters).length > 0 && (
          <Group mt="sm" gap="xs">
            {Object.entries(filters).map(([attr, values]) => (
              <Badge
                key={attr}
                variant="light"
                size="lg"
                rightSection={<CloseButton size="xs" onClick={() => setFilterValues(attr, [])} />}
              >
                {attrLabel(attr)}: {values.map(memberLabel).join(', ')}
              </Badge>
            ))}
          </Group>
        )}
      </Paper>

      <Group gap="xs">
        <Badge color="orange" variant="filled">
          {lastOp}
        </Badge>
        {data && (
          <Badge color={data.cuboid ? 'teal' : 'gray'} variant="light" leftSection={<IconDatabase size={12} />}>
            {data.source} · {data.elapsed_ms} ms
          </Badge>
        )}
      </Group>

      {error && (
        <Alert color="red" title="Không chạy được truy vấn OLAP">
          {error}
        </Alert>
      )}
      {loading && (
        <Group>
          <Loader size="sm" />
          <Text size="sm">Đang tính khối…</Text>
        </Group>
      )}

      {data && !error && (
        <>
          <Paper withBorder p="xs" style={{ overflowX: 'auto' }}>
            <Table withTableBorder withColumnBorders striped={false} highlightOnHover fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>
                    {attrLabel(data.rows)}
                    {data.cols ? ` \\ ${attrLabel(data.cols)}` : ''}
                  </Table.Th>
                  {data.cols
                    ? data.col_members.map((c) => <Table.Th key={c}>{memberLabel(c)}</Table.Th>)
                    : <Table.Th>{data.measure_label}</Table.Th>}
                  {data.cols && <Table.Th>Tổng</Table.Th>}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.row_members.map((r) => (
                  <Table.Tr key={r}>
                    <Table.Td
                      fw={600}
                      style={{ cursor: child ? 'pointer' : 'default', whiteSpace: 'nowrap' }}
                      title={child ? `Khoan xuống ${memberLabel(r)} → ${attrLabel(child)}` : undefined}
                      onClick={() => child && drillDown(r)}
                    >
                      {memberLabel(r)} {child && <IconChevronDown size={12} />}
                    </Table.Td>
                    {data.cols ? (
                      data.col_members.map((c) => {
                        const v = cellMap.get(`${r}\u0000${c}`)
                        return (
                          <Table.Td key={c} style={{ background: heat(v) }}>
                            {fmtValue(v, data.measure)}
                          </Table.Td>
                        )
                      })
                    ) : (
                      <Table.Td style={{ background: heat(data.row_totals[r]) }}>
                        {fmtValue(data.row_totals[r], data.measure)}
                      </Table.Td>
                    )}
                    {data.cols && <Table.Td fw={600}>{fmtValue(data.row_totals[r], data.measure)}</Table.Td>}
                  </Table.Tr>
                ))}
                <Table.Tr>
                  <Table.Td fw={700}>Tổng</Table.Td>
                  {data.cols &&
                    data.col_members.map((c) => (
                      <Table.Td key={c} fw={600}>
                        {fmtValue(data.col_totals[c], data.measure)}
                      </Table.Td>
                    ))}
                  <Table.Td fw={700}>{fmtValue(data.grand_total, data.measure)}</Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </Paper>

          {chartOption && (
            <Paper withBorder p="md">
              <ReactECharts option={chartOption} style={{ height: data.cols ? 380 : 300 }} notMerge />
            </Paper>
          )}

          <Accordion variant="contained">
            <Accordion.Item value="sql">
              <Accordion.Control>Xem câu truy vấn</Accordion.Control>
              <Accordion.Panel>
                <Code block>{data.sql}</Code>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </>
      )}
    </Stack>
  )
}
