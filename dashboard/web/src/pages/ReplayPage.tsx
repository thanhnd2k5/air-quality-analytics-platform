import {
  Alert,
  Badge,
  Group,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useMemo, useState } from 'react'

type Counts = {
  n: number
  tp: number
  fp: number
  fn: number
  tn: number
  f1: number | null
}

type Batch = {
  watermark: string
  n_issued: number
  n_alerts: number
  n_stations: number
  n_waiting: number
  n_scored: number
  model: Counts
  persistence: Counts
}

type ReplayRow = {
  station_key: number
  station_name: string
  origin_time: string
  target_time: string
  issued_watermark: string
  model_version: string
  probability: number
  alert: boolean
  persistence_alert: boolean
  origin_pm25: number
  origin_pm10: number | null
  origin_co: number | null
  source_file: string
  y_true: number | null
  suspect_spatiotemporal: boolean | null
  scored_watermark: string | null
}

type ReplayFile = {
  label: string
  task: string
  window: { start: string; end: string }
  batch_hours: number
  model_version: string
  probability_cutoff: number
  model_path: string
  source_matrix: string
  batches: Batch[]
  rows: ReplayRow[]
}

function stamp(value: string) {
  return value.replace('T', ' ').slice(0, 19)
}

function viewAt(rows: ReplayRow[], watermark: string): Array<ReplayRow & { status: 'waiting' | 'scored' }> {
  return rows
    .filter((row) => row.issued_watermark <= watermark)
    .map((row) => {
      const scored = row.scored_watermark != null && row.scored_watermark <= watermark
      if (!scored) {
        return { ...row, y_true: null, suspect_spatiotemporal: null, status: 'waiting' as const }
      }
      return { ...row, status: 'scored' as const }
    })
}

function pct(value: number | null) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

export function ReplayPage() {
  const [data, setData] = useState<ReplayFile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [watermark, setWatermark] = useState<string | null>(null)
  const [station, setStation] = useState<string | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  useEffect(() => {
    fetch('/replay/replay.json')
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        return response.json() as Promise<ReplayFile>
      })
      .then((payload) => {
        setData(payload)
        const last = payload.batches[payload.batches.length - 1]
        setWatermark(last?.watermark ?? null)
        setStation(payload.rows[0]?.station_name ?? null)
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Không đọc được phát lại'))
  }, [])

  const batch = data?.batches.find((item) => item.watermark === watermark) ?? null
  const visible = useMemo(
    () => (data && watermark ? viewAt(data.rows, watermark) : []),
    [data, watermark],
  )
  const stationRows = visible.filter((row) => row.station_name === station)
  const attention = visible
    .filter((row) => row.issued_watermark === watermark && row.alert)
    .sort((a, b) => b.probability - a.probability)
  const selected =
    visible.find((row) => `${row.station_name}|${row.origin_time}` === selectedKey) ??
    attention[0] ??
    null

  const chart = useMemo(() => {
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['Xác suất cảnh báo', 'PM2.5 giờ tới (đã tới)'] },
      grid: { left: 48, right: 48, top: 32, bottom: 48 },
      xAxis: { type: 'category', data: stationRows.map((row) => row.origin_time.slice(5, 16)) },
      yAxis: [
        { type: 'value', min: 0, max: 1, name: 'Xác suất' },
        { type: 'value', name: 'µg/m³' },
      ],
      series: [
        {
          name: 'Xác suất cảnh báo',
          type: 'line',
          data: stationRows.map((row) => Number(row.probability.toFixed(3))),
          showSymbol: false,
        },
        {
          name: 'PM2.5 giờ tới (đã tới)',
          type: 'line',
          yAxisIndex: 1,
          data: stationRows.map((row) => (row.status === 'scored' ? row.y_true : null)),
          showSymbol: false,
        },
      ],
    }
  }, [stationRows])

  if (error) {
    return (
      <Alert color="red" title="Không mở được phát lại">
        {error}
      </Alert>
    )
  }
  if (!data || !watermark || !batch) {
    return <Text>Đang đọc phát lại…</Text>
  }

  return (
    <Stack gap="md">
      <Alert color="orange" title={data.label}>
        Đây là phát lại 18–21/12/2016 theo từng mốc dữ liệu, không phải quan trắc trực tiếp. Mô hình khóa phát cảnh báo
        cho giờ tới. PM2.5 thực tế và cờ hậu kiểm chỉ hiện sau khi mốc dữ liệu đã đi qua giờ đó.
      </Alert>
      <div>
        <Title order={2}>Phát lại cảnh báo</Title>
        <Text size="sm" c="dimmed">
          {data.task}. Ngưỡng xác suất {data.probability_cutoff.toFixed(2)} · {data.model_version} · batch{' '}
          {data.batch_hours} giờ.
        </Text>
      </div>

      <Group align="flex-end">
        <Select
          label="Mốc dữ liệu"
          data={data.batches.map((item) => ({ value: item.watermark, label: stamp(item.watermark) }))}
          value={watermark}
          onChange={setWatermark}
          allowDeselect={false}
          w={220}
        />
        <Select
          label="Trạm"
          data={[...new Set(data.rows.map((row) => row.station_name))].sort().map((name) => ({
            value: name,
            label: name,
          }))}
          value={station}
          onChange={setStation}
          allowDeselect={false}
          w={200}
        />
      </Group>

      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Paper withBorder p="md">
          <Text size="xs" c="dimmed">Trạm đủ đặc trưng trong batch</Text>
          <Text fw={700} size="xl">{batch.n_stations}</Text>
        </Paper>
        <Paper withBorder p="md">
          <Text size="xs" c="dimmed">Cảnh báo mới</Text>
          <Text fw={700} size="xl">{batch.n_alerts}</Text>
        </Paper>
        <Paper withBorder p="md">
          <Text size="xs" c="dimmed">Đang chờ giờ tới</Text>
          <Text fw={700} size="xl">{batch.n_waiting}</Text>
        </Paper>
        <Paper withBorder p="md">
          <Text size="xs" c="dimmed">F1 đã chấm / persistence</Text>
          <Text fw={700} size="xl">{pct(batch.model.f1)} / {pct(batch.persistence.f1)}</Text>
        </Paper>
      </SimpleGrid>

      <Paper withBorder p="md">
        <Text fw={600} mb="xs">{station} — xác suất lúc phát, và PM2.5 giờ tới chỉ khi đã tới</Text>
        <ReactECharts option={chart} style={{ height: 280 }} />
      </Paper>

      <Paper withBorder p="md">
        <Text fw={600} mb="xs">Trạm cần chú ý tại mốc này</Text>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Trạm</Table.Th>
              <Table.Th>Giờ gốc</Table.Th>
              <Table.Th>Giờ mục tiêu</Table.Th>
              <Table.Th>Xác suất</Table.Th>
              <Table.Th>Trạng thái</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {attention.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={5}>Batch này không phát cảnh báo mới.</Table.Td>
              </Table.Tr>
            )}
            {attention.map((row) => {
              const key = `${row.station_name}|${row.origin_time}`
              return (
                <Table.Tr key={key} onClick={() => setSelectedKey(key)} style={{ cursor: 'pointer' }}>
                  <Table.Td>{row.station_name}</Table.Td>
                  <Table.Td>{stamp(row.origin_time)}</Table.Td>
                  <Table.Td>{stamp(row.target_time)}</Table.Td>
                  <Table.Td>{row.probability.toFixed(2)}</Table.Td>
                  <Table.Td>
                    <Badge color={row.status === 'scored' ? 'teal' : 'gray'} variant="light">
                      {row.status === 'scored' ? 'Đã chấm' : 'Chờ quan trắc'}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
      </Paper>

      {selected && (
        <Paper withBorder p="md">
          <Text fw={600} mb="xs">Truy vết cảnh báo {selected.station_name} · {stamp(selected.origin_time)}</Text>
          <Stack gap={4}>
            <Text size="sm">Mốc dữ liệu lúc phát: {stamp(selected.issued_watermark)}</Text>
            <Text size="sm">Giờ mục tiêu: {stamp(selected.target_time)}</Text>
            <Text size="sm">Mô hình: {selected.model_version} · {data.model_path}</Text>
            <Text size="sm">Ma trận đặc trưng: {data.source_matrix}</Text>
            <Text size="sm">Nguồn: {selected.source_file}</Text>
            <Text size="sm">
              PM2.5 lúc phát {selected.origin_pm25.toFixed(0)} µg/m³
              {selected.origin_pm10 != null ? ` · PM10 ${selected.origin_pm10.toFixed(0)}` : ''}
              {selected.origin_co != null ? ` · CO ${selected.origin_co.toFixed(0)}` : ''}
            </Text>
            <Text size="sm">Persistence lúc phát: {selected.persistence_alert ? 'có cảnh báo' : 'không'}</Text>
          </Stack>
          <Paper withBorder p="sm" mt="sm" bg="gray.0">
            <Text fw={600} size="sm">Hậu kiểm</Text>
            {selected.status === 'waiting' ? (
              <Text size="sm">Giờ mục tiêu chưa tới mốc đang xem. Chưa gắn actual và chưa gắn cờ review.</Text>
            ) : (
              <Text size="sm">
                PM2.5 giờ tới {selected.y_true?.toFixed(0)} µg/m³
                {selected.suspect_spatiotemporal
                  ? ' · Cờ review suspect_spatiotemporal: có. Cờ này dùng giờ sau, không phải đầu vào lúc phát.'
                  : ' · Cờ review suspect_spatiotemporal: không.'}
              </Text>
            )}
          </Paper>
        </Paper>
      )}
    </Stack>
  )
}
