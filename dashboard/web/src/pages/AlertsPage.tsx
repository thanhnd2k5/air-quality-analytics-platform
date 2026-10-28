import {
  Alert,
  Badge,
  Group,
  Loader,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useMemo, useState } from 'react'
import {
  fetchAlertMeta,
  fetchAlertSummary,
  fetchAlertTimeline,
  type AlertMeta,
  type AlertSummary,
  type AlertTimeline,
  type ConfusionMatrix,
} from '../api/alerts'
import { fetchStations, type Station } from '../api/stations'

function pct(v: number | null | undefined, d = 1) {
  return v == null ? '—' : `${(v * 100).toFixed(d)}%`
}

function num(v: number) {
  return v.toLocaleString('vi-VN')
}

const OUTCOME_COLOR: Record<string, string> = {
  TP: '#16a34a',
  FP: '#f59e0b',
  FN: '#dc2626',
}

function ConfusionCard({ title, m, highlight }: { title: string; m: ConfusionMatrix; highlight?: boolean }) {
  const cell = (label: string, v: number, bg: string) => (
    <Table.Td style={{ background: bg, textAlign: 'center' }}>
      <Text fw={700}>{num(v)}</Text>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
    </Table.Td>
  )
  return (
    <Paper withBorder p="md" style={highlight ? { borderColor: '#ea580c', borderWidth: 2 } : undefined}>
      <Group justify="space-between" mb="xs">
        <Text fw={600}>{title}</Text>
        <Badge variant="light" color={highlight ? 'orange' : 'gray'}>
          F1 {pct(m.f1)}
        </Badge>
      </Group>
      <Table withTableBorder withColumnBorders>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Thực tế \ Dự đoán</Table.Th>
            <Table.Th style={{ textAlign: 'center' }}>Cảnh báo</Table.Th>
            <Table.Th style={{ textAlign: 'center' }}>Không</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          <Table.Tr>
            <Table.Th>Vượt ngưỡng</Table.Th>
            {cell('TP — cảnh báo đúng', m.tp, 'rgba(22,163,74,0.15)')}
            {cell('FN — bỏ sót', m.fn, 'rgba(220,38,38,0.15)')}
          </Table.Tr>
          <Table.Tr>
            <Table.Th>Không vượt</Table.Th>
            {cell('FP — báo nhầm', m.fp, 'rgba(245,158,11,0.15)')}
            {cell('TN — đúng là sạch', m.tn, 'rgba(100,116,139,0.08)')}
          </Table.Tr>
        </Table.Tbody>
      </Table>
      <SimpleGrid cols={3} mt="sm">
        <div>
          <Text size="xs" c="dimmed">
            Precision
          </Text>
          <Text fw={600}>{pct(m.precision)}</Text>
        </div>
        <div>
          <Text size="xs" c="dimmed">
            Recall
          </Text>
          <Text fw={600}>{pct(m.recall)}</Text>
        </div>
        <div>
          <Text size="xs" c="dimmed">
            Bắt kịp lúc bắt đầu ô nhiễm
          </Text>
          <Text fw={600}>
            {num(m.onsets_detected)}/{num(m.onsets)} ({pct(m.onsets ? m.onsets_detected / m.onsets : null, 0)})
          </Text>
        </div>
      </SimpleGrid>
    </Paper>
  )
}

export function AlertsPage() {
  const [summary, setSummary] = useState<AlertSummary | null>(null)
  const [meta, setMeta] = useState<AlertMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [stationKey, setStationKey] = useState<string>('4')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [timeline, setTimeline] = useState<AlertTimeline | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([fetchAlertSummary('test'), fetchAlertMeta(), fetchStations()])
      .then(([s, m, st]) => {
        setSummary(s)
        setMeta(m)
        setStations(st)
        setDateFrom(m.default_from)
        setDateTo(m.default_to)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!dateFrom || !dateTo) return
    let cancelled = false
    setLoading(true)
    fetchAlertTimeline({ station_key: Number(stationKey), date_from: dateFrom, date_to: dateTo })
      .then((t) => {
        if (!cancelled) {
          setTimeline(t)
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
  }, [stationKey, dateFrom, dateTo])

  const chartOption = useMemo(() => {
    const s = timeline?.series ?? []
    const x = s.map((p) => p.target_time.replace('T', ' ').slice(0, 13) + 'h')
    const threshold = timeline?.alert_threshold ?? 115
    const marks = (outcome: string) =>
      s.map((p) => (p.outcome === outcome ? p.actual_pm25 : null))
    return {
      tooltip: { trigger: 'axis' },
      legend: {
        top: 0,
        data: ['PM2.5 thực tế', 'Xác suất cảnh báo', 'Cảnh báo đúng (TP)', 'Báo nhầm (FP)', 'Bỏ sót (FN)'],
      },
      grid: { left: 56, right: 56, top: 56, bottom: 40 },
      xAxis: { type: 'category', data: x, axisLabel: { hideOverlap: true } },
      yAxis: [
        { type: 'value', name: 'PM2.5 (µg/m³)', splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } } },
        { type: 'value', name: 'P(cảnh báo)', min: 0, max: 1 },
      ],
      series: [
        {
          name: 'PM2.5 thực tế',
          type: 'line',
          data: s.map((p) => p.actual_pm25),
          showSymbol: false,
          lineStyle: { color: '#334155' },
          itemStyle: { color: '#334155' },
          markLine: {
            symbol: 'none',
            label: { formatter: `Ngưỡng ${threshold}` },
            lineStyle: { color: '#dc2626', type: 'dashed' },
            data: [{ yAxis: threshold }],
          },
        },
        {
          name: 'Xác suất cảnh báo',
          type: 'line',
          yAxisIndex: 1,
          data: s.map((p) => p.predicted_proba),
          showSymbol: false,
          areaStyle: { opacity: 0.12 },
          lineStyle: { color: '#ea580c', width: 1 },
          itemStyle: { color: '#ea580c' },
        },
        ...(['TP', 'FP', 'FN'] as const).map((o) => ({
          name: o === 'TP' ? 'Cảnh báo đúng (TP)' : o === 'FP' ? 'Báo nhầm (FP)' : 'Bỏ sót (FN)',
          type: 'scatter',
          data: marks(o),
          symbolSize: 7,
          itemStyle: { color: OUTCOME_COLOR[o] },
        })),
      ],
    }
  }, [timeline])

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Cảnh báo vượt ngưỡng PM2.5</Title>
        <Text size="sm" c="dimmed">
          Giờ tới PM2.5 có từ {summary?.alert_threshold ?? 115} µg/m³ trở lên hay không. Đánh giá trên 07–12/2016.
        </Text>
      </div>

      {error && (
        <Alert color="red" title="Không tải được dữ liệu cảnh báo">
          {error}
        </Alert>
      )}

      {summary && (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <ConfusionCard title="Mô hình HistGradientBoosting" m={summary.model} highlight />
          <ConfusionCard title="Giờ này đã vượt ngưỡng" m={summary.persistence} />
        </SimpleGrid>
      )}

      <Paper withBorder p="md">
        <Group align="flex-end" gap="sm" mb="sm" wrap="wrap">
          <Select
            label="Trạm"
            data={stations.map((s) => ({ value: String(s.station_key), label: s.station_name }))}
            value={stationKey}
            onChange={(v) => v && setStationKey(v)}
            w={220}
          />
          <TextInput
            label="Từ ngày"
            type="date"
            value={dateFrom}
            min={meta?.data_min}
            max={meta?.data_max}
            onChange={(e) => setDateFrom(e.currentTarget.value)}
          />
          <TextInput
            label="Đến ngày"
            type="date"
            value={dateTo}
            min={meta?.data_min}
            max={meta?.data_max}
            onChange={(e) => setDateTo(e.currentTarget.value)}
          />
          {loading && <Loader size="sm" />}
        </Group>
        <ReactECharts option={chartOption} style={{ height: 380 }} notMerge />
      </Paper>

      {summary && (
        <Paper withBorder p="md">
          <Text fw={600} mb="xs">
            Theo trạm (tập test)
          </Text>
          <Table striped highlightOnHover withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Trạm</Table.Th>
                <Table.Th>Số giờ vượt ngưỡng</Table.Th>
                <Table.Th>F1 mô hình</Table.Th>
                <Table.Th>F1 cách đơn giản</Table.Th>
                <Table.Th>Recall mô hình</Table.Th>
                <Table.Th>Recall cách đơn giản</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {summary.stations.map((s) => (
                <Table.Tr key={s.station_key}>
                  <Table.Td>{s.station_name}</Table.Td>
                  <Table.Td>{num(s.positives)}</Table.Td>
                  <Table.Td fw={600}>{pct(s.f1_model)}</Table.Td>
                  <Table.Td>{pct(s.f1_persistence)}</Table.Td>
                  <Table.Td>{pct(s.recall_model)}</Table.Td>
                  <Table.Td>{pct(s.recall_persistence)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  )
}
