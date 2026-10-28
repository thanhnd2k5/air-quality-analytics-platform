import {
  Alert,
  Group,
  Paper,
  Select,
  SimpleGrid,
  Stack,
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
  const selected = stationRows
    .filter((row) => row.issued_watermark === watermark && row.alert)
    .sort((a, b) => a.origin_time.localeCompare(b.origin_time))
    .at(-1)

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
        cho giờ tới. Số đo thật chỉ hiện sau khi mốc dữ liệu đã đi qua giờ đó.
      </Alert>
      <div>
        <Title order={2}>Phát lại cảnh báo</Title>
        <Text size="sm" c="dimmed">
          Chọn một mốc dữ liệu. Cảnh báo phát cho giờ tới. Số đo thật chỉ hiện khi mốc đã đi qua giờ đó.
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
          <Text size="xs" c="dimmed">Trạm có đủ dữ liệu</Text>
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
          <Text size="xs" c="dimmed">F1 mô hình / giờ trước</Text>
          <Text fw={700} size="xl">{pct(batch.model.f1)} / {pct(batch.persistence.f1)}</Text>
        </Paper>
      </SimpleGrid>

      <Paper withBorder p="md">
        <Text fw={600} mb="xs">{station} — xác suất lúc phát, và PM2.5 giờ tới chỉ khi đã tới</Text>
        <ReactECharts option={chart} style={{ height: 280 }} />
      </Paper>

      {selected ? (
        <Paper withBorder p="md">
          <Text fw={600} mb="xs">
            {selected.station_name} · phát lúc {stamp(selected.origin_time)}
          </Text>
          <Stack gap={4}>
            <Text size="sm">Giờ cần dự báo: {stamp(selected.target_time)}</Text>
            <Text size="sm">PM2.5 lúc phát: {selected.origin_pm25.toFixed(0)} µg/m³</Text>
            <Text size="sm">
              Cách lấy nguyên giờ trước: {selected.persistence_alert ? 'có cảnh báo' : 'không cảnh báo'}
            </Text>
            {selected.status === 'waiting' ? (
              <Text size="sm">Giờ cần dự báo chưa tới mốc đang xem, nên chưa có số đo thật.</Text>
            ) : (
              <Text size="sm">Số đo thật của giờ đó: {selected.y_true?.toFixed(0)} µg/m³</Text>
            )}
          </Stack>
        </Paper>
      ) : (
        <Paper withBorder p="md">
          <Text size="sm">Mốc này không phát cảnh báo mới cho {station}.</Text>
        </Paper>
      )}
    </Stack>
  )
}
