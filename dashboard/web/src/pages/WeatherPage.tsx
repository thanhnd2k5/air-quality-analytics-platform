import {
  Alert,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useState } from 'react'
import { fetchOverviewMeta, type OverviewMeta } from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import {
  fetchWeather,
  type ScatterVariable,
  type WeatherResponse,
} from '../api/weather'
import { DateStationFilters } from '../components/DateStationFilters'

const SCATTER_OPTIONS: { value: ScatterVariable; label: string }[] = [
  { value: 'temperature_c_avg', label: 'Nhiệt độ (°C)' },
  { value: 'relative_humidity_pct_avg', label: 'Độ ẩm (%)' },
  { value: 'wind_speed_m_s_avg', label: 'Gió (m/s)' },
  { value: 'rain_mm_sum', label: 'Mưa (mm)' },
  { value: 'cloud_cover_pct_avg', label: 'Mây (%)' },
]

export function WeatherPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [scatterVar, setScatterVar] =
    useState<ScatterVariable>('temperature_c_avg')
  const [data, setData] = useState<WeatherResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchOverviewMeta(), fetchStations()])
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
    fetchWeather({
      date_from: dateFrom,
      date_to: dateTo,
      station_key: stationKey ? Number(stationKey) : null,
      scatter_variable: scatterVar,
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
  }, [dateFrom, dateTo, stationKey, scatterVar])

  const scatterLabel =
    SCATTER_OPTIONS.find((o) => o.value === scatterVar)?.label ?? scatterVar

  const seriesOption = {
    color: ['#0d9488', '#64748b'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['PM2.5', 'Nhiệt độ'] },
    grid: { left: 48, right: 48, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: data?.series.map((p) => p.date_day) ?? [],
      axisLabel: { hideOverlap: true },
    },
    yAxis: [
      {
        type: 'value',
        name: 'PM2.5',
        splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
      },
      { type: 'value', name: '°C' },
    ],
    series: [
      {
        name: 'PM2.5',
        type: 'line',
        showSymbol: false,
        data: data?.series.map((p) => p.pm25_ug_m3_avg) ?? [],
      },
      {
        name: 'Nhiệt độ',
        type: 'line',
        yAxisIndex: 1,
        showSymbol: false,
        data: data?.series.map((p) => p.temperature_c_avg) ?? [],
      },
    ],
  }

  const scatterOption = {
    color: ['#0d9488'],
    tooltip: {
      trigger: 'item',
      formatter: (p: { value?: [number, number]; data?: [number, number] }) => {
        const v = p.value ?? p.data
        if (!v) return ''
        return `${scatterLabel}: ${v[0]}<br/>PM2.5: ${v[1]}`
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 48 },
    xAxis: {
      type: 'value',
      name: scatterLabel,
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.3 } },
    },
    yAxis: {
      type: 'value',
      name: 'PM2.5 µg/m³',
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.3 } },
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 8,
        data:
          data?.scatter.map((p) => [p.weather_value, p.pm25_ug_m3_avg]) ?? [],
      },
    ],
  }

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Thời tiết</Title>
        <Text size="sm" c="dimmed">
          PM2.5 và điều kiện thời tiết (mart_pollution_weather)
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
          label="Biến scatter"
          data={SCATTER_OPTIONS}
          value={scatterVar}
          onChange={(v) => v && setScatterVar(v as ScatterVariable)}
          w={200}
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
          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Chuỗi thời gian PM2.5 vs nhiệt độ
            </Text>
            <ReactECharts option={seriesOption} style={{ height: 340 }} />
          </Paper>
          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Scatter PM2.5 vs {scatterLabel}
            </Text>
            <ReactECharts option={scatterOption} style={{ height: 360 }} />
          </Paper>
        </>
      )}
    </Stack>
  )
}
