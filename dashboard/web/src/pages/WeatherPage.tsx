import { Group, Select, Stack } from '@mantine/core'
import { useEffect, useState } from 'react'
import { fetchOverviewMeta, type OverviewMeta } from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import {
  fetchWeather,
  type ScatterVariable,
  type WeatherResponse,
  type WeatherSeriesPoint,
} from '../api/weather'
import { Chart } from '../components/Chart'
import { DateStationFilters } from '../components/DateStationFilters'
import { Metric } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { FilterBar, Panel } from '../components/Panel'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { NEUTRAL_SERIES, SERIES } from '../theme'

const VARIABLES: {
  value: ScatterVariable
  /** Dropdown heading; related variables sit together. */
  group: string
  label: string
  seriesName: string
  unit: string
  /** Step used to read the slope ("PM2.5 changes by … per +step unit"). */
  step: number
  up: string
  down: string
  flat: string
}[] = [
  {
    value: 'temperature_c_avg',
    group: 'Nhiệt – ẩm',
    label: 'Nhiệt độ (°C)',
    seriesName: 'Nhiệt độ',
    unit: '°C',
    step: 5,
    up: 'Ngày nóng hơn thường có PM2.5 cao hơn.',
    down: 'Ngày nóng hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng nhiệt độ trong khoảng ngày này.',
  },
  {
    value: 'dew_point_c_avg',
    group: 'Nhiệt – ẩm',
    label: 'Điểm sương (°C)',
    seriesName: 'Điểm sương',
    unit: '°C',
    step: 5,
    up: 'Ngày điểm sương cao hơn (không khí chứa nhiều hơi nước) thường có PM2.5 cao hơn.',
    down: 'Ngày điểm sương cao hơn (không khí chứa nhiều hơi nước) thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng điểm sương trong khoảng ngày này.',
  },
  {
    value: 'relative_humidity_pct_avg',
    group: 'Nhiệt – ẩm',
    label: 'Độ ẩm (%)',
    seriesName: 'Độ ẩm',
    unit: '%',
    step: 10,
    up: 'Ngày ẩm hơn thường có PM2.5 cao hơn.',
    down: 'Ngày ẩm hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng độ ẩm trong khoảng ngày này.',
  },
  {
    value: 'wind_speed_m_s_avg',
    group: 'Gió – áp suất',
    label: 'Gió (m/s)',
    seriesName: 'Gió',
    unit: 'm/s',
    step: 1,
    up: 'Ngày gió mạnh hơn thường có PM2.5 cao hơn.',
    down: 'Ngày gió mạnh hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng tốc độ gió trong khoảng ngày này.',
  },
  {
    value: 'pressure_hpa_avg',
    group: 'Gió – áp suất',
    label: 'Áp suất (hPa)',
    seriesName: 'Áp suất',
    unit: 'hPa',
    step: 5,
    up: 'Ngày áp suất cao hơn thường có PM2.5 cao hơn.',
    down: 'Ngày áp suất cao hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng áp suất trong khoảng ngày này.',
  },
  {
    value: 'rain_mm_sum',
    group: 'Mưa – mây',
    label: 'Lượng mưa (mm/ngày)',
    seriesName: 'Lượng mưa',
    unit: 'mm',
    step: 1,
    up: 'Ngày mưa nhiều hơn thường có PM2.5 cao hơn.',
    down: 'Ngày mưa nhiều hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng lượng mưa trong khoảng ngày này.',
  },
  {
    value: 'cloud_cover_pct_avg',
    group: 'Mưa – mây',
    label: 'Mây che phủ (%)',
    seriesName: 'Mây che phủ',
    unit: '%',
    step: 10,
    up: 'Ngày nhiều mây hơn thường có PM2.5 cao hơn.',
    down: 'Ngày nhiều mây hơn thường có PM2.5 thấp hơn.',
    flat: 'PM2.5 ít đi cùng độ che phủ mây trong khoảng ngày này.',
  },
]

const VARIABLE_OPTIONS = [...new Set(VARIABLES.map((v) => v.group))].map((group) => ({
  group,
  items: VARIABLES.filter((v) => v.group === group).map((v) => ({ value: v.value, label: v.label })),
}))

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

/** Least-squares line and Pearson r over the plotted days (null when too few to read). */
function fitLine(data: WeatherResponse) {
  const pairs = data.scatter.filter(
    (point): point is { date_day: string; weather_value: number; pm25_ug_m3_avg: number } =>
      point.weather_value != null &&
      point.pm25_ug_m3_avg != null &&
      Number.isFinite(point.weather_value) &&
      Number.isFinite(point.pm25_ug_m3_avg),
  )
  if (pairs.length < 10) return null
  const xs = pairs.map((p) => p.weather_value)
  const ys = pairs.map((p) => p.pm25_ug_m3_avg)
  const r = pearson(xs, ys)
  if (r == null) return null
  const meanX = xs.reduce((s, v) => s + v, 0) / xs.length
  const meanY = ys.reduce((s, v) => s + v, 0) / ys.length
  let sxy = 0
  let sxx = 0
  for (let i = 0; i < xs.length; i += 1) {
    sxy += (xs[i] - meanX) * (ys[i] - meanY)
    sxx += (xs[i] - meanX) ** 2
  }
  const slope = sxy / sxx
  return {
    n: pairs.length,
    r,
    slope,
    intercept: meanY - slope * meanX,
    x0: Math.min(...xs),
    x1: Math.max(...xs),
  }
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

function dayLabel(iso: string) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(2, 4)}`
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
  const days = shown?.series.map((point) => point.date_day) ?? []

  // One tooltip for both panels: the day, PM2.5 and the weather variable, each with its unit.
  const tooltipFor = (params: { dataIndex: number }[]) => {
    const point = shown?.series[params[0]?.dataIndex ?? -1]
    if (!point) return ''
    const fmt = (v: number | null | undefined, unit: string) =>
      v == null ? '—' : `${v.toFixed(1)}${unit === '%' ? '' : ' '}${unit}`
    return [
      `<b>${point.date_day.slice(8, 10)}/${point.date_day.slice(5, 7)}/${point.date_day.slice(0, 4)}</b>`,
      `PM2.5: <b>${fmt(point.pm25_ug_m3_avg, 'µg/m³')}</b>`,
      `${spec.seriesName}: <b>${fmt(seriesValues(point), spec.unit)}</b>`,
    ].join('<br/>')
  }

  // PM2.5 above, the weather variable below, sharing the day axis (no second y-scale).
  const seriesOption = {
    tooltip: { trigger: 'axis', formatter: tooltipFor },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: { data: ['PM2.5', spec.seriesName] },
    grid: [
      { left: 8, right: 16, top: 48, height: '46%', containLabel: true },
      { left: 8, right: 16, bottom: 8, height: '26%', containLabel: true },
    ],
    xAxis: [
      { type: 'category', data: days, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: days, gridIndex: 1, axisLabel: { formatter: dayLabel } },
    ],
    yAxis: [
      { type: 'value', name: 'PM2.5 (µg/m³)', gridIndex: 0 },
      { type: 'value', name: `${spec.seriesName} (${spec.unit})`, gridIndex: 1, splitNumber: 2, scale: true },
    ],
    series: [
      {
        name: 'PM2.5',
        type: 'line',
        showSymbol: false,
        color: SERIES.blue,
        data: shown?.series.map((point) => point.pm25_ug_m3_avg) ?? [],
      },
      {
        name: spec.seriesName,
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        color: SERIES.orange,
        data: shown?.series.map((point) => seriesValues(point)) ?? [],
      },
    ],
  }

  const fit = shown ? fitLine(shown) : null
  const perStep = fit ? fit.slope * spec.step : null

  const scatterOption = {
    tooltip: {
      trigger: 'item',
      formatter: (item: { value?: [number, number]; data?: [number, number] }) => {
        const value = item.value ?? item.data
        if (!value) return ''
        return `${spec.label}: <b>${value[0]}</b><br/>PM2.5: <b>${value[1]}</b> µg/m³`
      },
    },
    grid: { left: 8, right: 24, top: 36, bottom: 32, containLabel: true },
    xAxis: {
      type: 'value',
      name: spec.label,
      nameLocation: 'middle',
      nameGap: 28,
      scale: true,
      axisLine: { show: true },
      splitLine: { show: false },
    },
    // PM2.5 is never negative; pinning 0 also clips the trend line where it would dip below.
    yAxis: { type: 'value', name: 'PM2.5 (µg/m³)', min: 0 },
    series: [
      {
        type: 'scatter',
        color: SERIES.blue,
        itemStyle: { opacity: 0.7, borderColor: '#fff', borderWidth: 1 },
        data: shown?.scatter.map((point) => [point.weather_value, point.pm25_ug_m3_avg]) ?? [],
      },
      ...(fit
        ? [
            {
              type: 'line',
              name: 'Đường xu hướng',
              silent: true,
              showSymbol: false,
              color: NEUTRAL_SERIES.strong,
              lineStyle: { type: 'dashed', width: 1.5 },
              z: 3,
              data: [
                [fit.x0, fit.intercept + fit.slope * fit.x0],
                [fit.x1, fit.intercept + fit.slope * fit.x1],
              ],
            },
          ]
        : []),
    ],
  }

  return (
    <Stack gap="lg">
      <PageHeader
        title="Thời tiết"
        description="PM2.5 đi cùng nhiệt độ, độ ẩm, gió, áp suất, mưa và mây như thế nào. Mỗi điểm là một ngày."
      />

      <FilterBar busy={loading && shown != null}>
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
          data={VARIABLE_OPTIONS}
          value={scatterVar}
          onChange={(value) => value && setScatterVar(value as ScatterVariable)}
          allowDeselect={false}
          maxDropdownHeight={420}
          w={220}
        />
      </FilterBar>

      {error && <ErrorAlert title="Không tải được dữ liệu thời tiết" message={error} />}
      {!shown && loading && !error && <LoadingBlock height={340} />}

      {shown && !error && (
        <>
          <Panel
            title={`PM2.5 và ${spec.seriesName.toLowerCase()} theo ngày`}
            description="Hai tầng dùng chung trục thời gian; rê chuột để xem cùng một ngày."
            busy={loading}
          >
            <Chart
              key={`series-${scatterVar}`}
              option={seriesOption}
              height={380}
              label={`PM2.5 và ${spec.seriesName} theo ngày, hai tầng dùng chung trục thời gian.`}
            />
          </Panel>
          <Panel
            title={`Tương quan PM2.5 và ${spec.seriesName.toLowerCase()}`}
            description={`${readCloud(scatterVar, shown)}${fit ? ' Đường đứt là xu hướng tuyến tính.' : ''}`}
            busy={loading}
            actions={
              fit &&
              perStep != null && (
                <Group gap="xl" wrap="nowrap">
                  <Metric label="Hệ số tương quan r" value={fit.r.toFixed(2)} hint={`${fit.n} ngày`} size="sm" />
                  <Metric
                    label="Độ dốc"
                    value={`${perStep >= 0 ? '+' : '−'}${Math.abs(perStep).toFixed(1)}`}
                    unit="µg/m³"
                    hint={`mỗi +${spec.step}${spec.unit === '%' ? '' : ' '}${spec.unit} ${spec.seriesName.toLowerCase()}`}
                    size="sm"
                  />
                </Group>
              )
            }
          >
            <Chart
              key={`scatter-${scatterVar}`}
              option={scatterOption}
              height={360}
              label={`Biểu đồ phân tán PM2.5 theo ${spec.label}, mỗi điểm là một ngày.`}
            />
          </Panel>
        </>
      )}
    </Stack>
  )
}
