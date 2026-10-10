import {
  Alert,
  Group,
  Loader,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useState } from 'react'
import {
  fetchPredictionMeta,
  fetchPredictions,
  type PredictionMeta,
  type PredictionsResponse,
} from '../api/predictions'
import { fetchStations, type Station } from '../api/stations'
import { DateStationFilters } from '../components/DateStationFilters'

function fmt(n: number | null | undefined, d = 2) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(d)
}

export function PredictionsPage() {
  const [meta, setMeta] = useState<PredictionMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [split, setSplit] = useState<string | null>(null)
  const [data, setData] = useState<PredictionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchPredictionMeta(), fetchStations()])
      .then(([m, s]) => {
        setMeta(m)
        setStations(s)
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
    fetchPredictions({
      date_from: dateFrom,
      date_to: dateTo,
      station_key: stationKey ? Number(stationKey) : null,
      split,
    })
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [dateFrom, dateTo, stationKey, split])

  const chartOption = {
    color: ['#334155', '#0d9488', '#94a3b8'],
    tooltip: { trigger: 'axis' },
    legend: { data: ['Thực tế', 'HistGB', 'Persistence'] },
    grid: { left: 48, right: 24, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: data?.series.map((p) => p.target_time.replace('T', ' ').slice(0, 16)) ?? [],
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: 'PM2.5',
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
    },
    series: [
      {
        name: 'Thực tế',
        type: 'line',
        showSymbol: false,
        data: data?.series.map((p) => p.actual_pm25) ?? [],
      },
      {
        name: 'HistGB',
        type: 'line',
        showSymbol: false,
        data: data?.series.map((p) => p.predicted_pm25) ?? [],
      },
      {
        name: 'Persistence',
        type: 'line',
        showSymbol: false,
        data: data?.series.map((p) => p.predicted_pm25_persistence) ?? [],
      },
    ],
  }

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Dự báo</Title>
        <Text size="sm" c="dimmed">
          PM2.5(t+1h) — mart_pm25_predictions
          {data?.model_version ? ` · ${data.model_version}` : ''}
        </Text>
      </div>

      <Group align="flex-end" wrap="wrap">
        <DateStationFilters
          dateFrom={dateFrom}
          dateTo={dateTo}
          stationKey={stationKey}
          stations={stations}
          dataMin={meta?.data_min}
          dataMax={meta?.data_max}
          onDateFrom={setDateFrom}
          onDateTo={setDateTo}
          onStationKey={setStationKey}
        />
        <Select
          label="Split"
          clearable
          placeholder="Tất cả"
          data={[
            { value: 'train', label: 'train' },
            { value: 'val', label: 'val' },
            { value: 'test', label: 'test' },
          ]}
          value={split}
          onChange={setSplit}
          w={140}
        />
      </Group>

      {loading && (
        <Group>
          <Loader size="sm" />
          <Text size="sm">Đang tải…</Text>
        </Group>
      )}
      {error && (
        <Alert color="red" title="Lỗi">
          {error}
        </Alert>
      )}

      {!loading && !error && data && (
        <>
          <SimpleGrid cols={{ base: 1, sm: data.metrics.length || 1 }} spacing="sm">
            {data.metrics.map((m) => (
              <Paper key={m.split} withBorder p="md" radius="sm">
                <Text size="xs" c="dimmed" tt="uppercase">
                  {m.split} · n={m.n}
                </Text>
                <Text fw={600} size="lg">
                  MAE HistGB {fmt(m.mae_model)}
                </Text>
                <Text size="sm" c="dimmed">
                  MAE persistence {fmt(m.mae_persistence)}
                </Text>
              </Paper>
            ))}
          </SimpleGrid>

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Chuỗi actual vs predicted
              {stationKey
                ? ''
                : ' (trung bình theo giờ mọi trạm — chọn 1 trạm để rõ hơn)'}
            </Text>
            {data.series.length === 0 ? (
              <Text size="sm" c="dimmed">
                Không có điểm trong khoảng chọn.
              </Text>
            ) : (
              <ReactECharts option={chartOption} style={{ height: 380 }} />
            )}
          </Paper>

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Metric theo split (trong filter)
            </Text>
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Split</Table.Th>
                  <Table.Th>n</Table.Th>
                  <Table.Th>MAE model</Table.Th>
                  <Table.Th>MAE persistence</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.metrics.map((m) => (
                  <Table.Tr key={m.split}>
                    <Table.Td>{m.split}</Table.Td>
                    <Table.Td>{m.n}</Table.Td>
                    <Table.Td>{fmt(m.mae_model)}</Table.Td>
                    <Table.Td>{fmt(m.mae_persistence)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </>
      )}
    </Stack>
  )
}
