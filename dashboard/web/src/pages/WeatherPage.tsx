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
  type WeatherSeriesPoint,
} from '../api/weather'
import { DateStationFilters } from '../components/DateStationFilters'

const VARIABLES: {
  value: ScatterVariable
  label: string
  seriesName: string
  unit: string
  up: string
  down: string
  flat: string
}[] = [
  {
    value: 'relative_humidity_pct_avg',
    label: 'Độ ẩm (%)',
    seriesName: 'Độ ẩm',
    unit: '%',
    up: 'Ngày ẩm hơn thường có PM2.5 cao hơn.',
    down: 'Ngày ẩm hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng độ ẩm trong khoảng ngày này.',
  },
  {
    value: 'wind_speed_m_s_avg',
    label: 'Gió (m/s)',
    seriesName: 'Gió',
    unit: 'm/s',
    up: 'Ngày gió mạnh hơn thường có PM2.5 cao hơn.',
    down: 'Ngày gió mạnh hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng tốc độ gió trong khoảng ngày này.',
  },
  {
    value: 'temperature_c_avg',
    label: 'Nhiệt độ (°C)',
    seriesName: 'Nhiệt độ',
    unit: '°C',
    up: 'Ngày nóng hơn thường có PM2.5 cao hơn.',
    down: 'Ngày nóng hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng nhiệt độ trong khoảng ngày này.',
  },
]

function variableOf(value: ScatterVariable) {
  return VARIABLES.find((item) => item.value === value) ?? VARIABLES[0]
}

function pearson(xs: number[], ys: number[]): number | null {
  const n = xs.length
  if (n < 2) return null
  const meanX = xs.reduce((sum, value) => sum + value, 0) / n
  const meanY = ys.reduce((sum, value) => sum + value, 0) / n
  let numerator = 0
  let spreadX = 0
  let spreadY = 0
  for (let i = 0; i < n; i += 1) {
    const dx = xs[i] - meanX
    const dy = ys[i] - meanY
    numerator += dx * dy
    spreadX += dx * dx
    spreadY += dy * dy
  }
  if (spreadX === 0 || spreadY === 0) return null
  return numerator / Math.sqrt(spreadX * spreadY)
}

function readCloud(value: ScatterVariable, data: WeatherResponse): string {
  const spec = variableOf(value)
  const pairs = data.scatter.filter(
    (point): point is { date_day: string; weather_value: number; pm25_ug_m3_avg: number } =>
      point.weather_value != null &&
      point.pm25_ug_m3_avg != null &&
      Number.isFinite(point.weather_value) &&
      Number.isFinite(point.pm25_ug_m3_avg),
  )
  if (data.scatter_variable !== value) {
    return ''
  }
  if (pairs.length < 10) {
    return `Khoảng ngày này có ${pairs.length} ngày đủ số, chưa đủ để đọc độ dốc.`
  }
  const association = pearson(
    pairs.map((point) => point.weather_value),
    pairs.map((point) => point.pm25_ug_m3_avg),
  )
  if (association == null) {
    return `Biến này gần như không đổi trên ${pairs.length} ngày đang xem, nên không có độ dốc để đọc.`
  }
  const slope = Math.abs(association) < 0.2 ? spec.flat : association > 0 ? spec.up : spec.down
  const grain = data.station_key == null ? 'trung bình 12 trạm' : 'một trạm'
  return `${slope} Mỗi điểm là một ngày (${grain}).`
}

export function WeatherPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [scatterVar, setScatterVar] = useState<ScatterVariable>('relative_humidity_pct_avg')
  const [data, setData] = useState<WeatherResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchOverviewMeta(), fetchStations()])
      .then(([overview, stationList]) => {
        setMeta(overview)
        setStations(stationList)
        setDateFrom(overview.default_from)
        setDateTo(overview.default_to)
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
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [dateFrom, dateTo, stationKey, scatterVar])

  const spec = variableOf(scatterVar)
  const shown = data && data.scatter_variable === scatterVar ? data : null
  const seriesValues = (point: WeatherSeriesPoint) => point[spec.value]

  const seriesOption = {
    color: ['#0d9488', '#64748b'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['PM2.5', spec.seriesName] },
    grid: { left: 48, right: 48, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: shown?.series.map((point) => point.date_day) ?? [],
      axisLabel: { hideOverlap: true },
    },
    yAxis: [
      {
        type: 'value',
        name: 'PM2.5',
        splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
      },
      { type: 'value', name: spec.unit },
    ],
    series: [
      {
        name: 'PM2.5',
        type: 'line',
        showSymbol: false,
        data: shown?.series.map((point) => point.pm25_ug_m3_avg) ?? [],
      },
      {
        name: spec.seriesName,
        type: 'line',
        yAxisIndex: 1,
        showSymbol: false,
        data: shown?.series.map((point) => seriesValues(point)) ?? [],
      },
    ],
  }

  const scatterOption = {
    color: ['#0d9488'],
    tooltip: {
      trigger: 'item',
      formatter: (item: { value?: [number, number]; data?: [number, number] }) => {
        const value = item.value ?? item.data
        if (!value) return ''
        return `${spec.label}: ${value[0]}<br/>PM2.5: ${value[1]}`
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 48 },
    xAxis: {
      type: 'value',
      name: spec.label,
      nameLocation: 'middle',
      nameGap: 28,
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
        data: shown?.scatter.map((point) => [point.weather_value, point.pm25_ug_m3_avg]) ?? [],
      },
    ],
  }

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Thời tiết</Title>
        <Text size="sm" c="dimmed">
          PM2.5 đi cùng độ ẩm, gió và nhiệt độ. Mỗi điểm là một ngày.
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
          label="Biến thời tiết"
          data={VARIABLES.map((item) => ({ value: item.value, label: item.label }))}
          value={scatterVar}
          onChange={(value) => value && setScatterVar(value as ScatterVariable)}
          allowDeselect={false}
          w={220}
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

      {!loading && !error && shown && (
        <>
          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Chuỗi thời gian PM2.5 và {spec.label}
            </Text>
            <ReactECharts key={`series-${scatterVar}`} option={seriesOption} notMerge style={{ height: 340 }} />
          </Paper>
          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Biểu đồ phân tán PM2.5 và {spec.label}
            </Text>
            <Text size="sm" mb="xs">
              {readCloud(scatterVar, shown)}
            </Text>
            <ReactECharts key={`scatter-${scatterVar}`} option={scatterOption} notMerge style={{ height: 360 }} />
          </Paper>
        </>
      )}
    </Stack>
  )
}
