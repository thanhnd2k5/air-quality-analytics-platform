import { Group, Select, Stack } from '@mantine/core'
import { useEffect, useState } from 'react'
import { fetchOverviewMeta, type OverviewMeta } from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import {
  fetchWeather,
  fetchWindRose,
  type ScatterVariable,
  type WeatherResponse,
  type WeatherSeriesPoint,
  type WindRosePoint,
  type WindRoseResponse,
} from '../api/weather'
import { Chart } from '../components/Chart'
import { DateStationFilters } from '../components/DateStationFilters'
import { Metric } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { FilterBar, Panel } from '../components/Panel'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { fmtNum, fmtPct, fmtSigned } from '../format'
import { INK, NEUTRAL_SERIES, SERIES } from '../theme'
import { compassLabel } from '../wind'

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

// Direction is categorical (no daily mean, no scatter): picking it shows a wind rose instead.
const WIND_DIRECTION = 'wind_direction'
type Variable = ScatterVariable | typeof WIND_DIRECTION

const VARIABLE_OPTIONS = [...new Set(VARIABLES.map((v) => v.group))].map((group) => ({
  group,
  items: VARIABLES.filter((v) => v.group === group).flatMap((v) => [
    { value: v.value, label: v.label },
    ...(v.value === 'wind_speed_m_s_avg' ? [{ value: WIND_DIRECTION, label: 'Hướng gió' }] : []),
  ]),
}))

function variableOf(value: Variable) {
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

/** Polar bars, north on top and clockwise; petal length = share of hours with PM2.5 ≥ 115. */
function windRoseOption(rose: WindRosePoint[]) {
  const total = rose.reduce((sum, p) => sum + p.hours, 0)
  return {
    tooltip: {
      trigger: 'item',
      formatter: (item: { dataIndex: number }) => {
        const p = rose[item.dataIndex]
        if (!p) return ''
        return [
          `<b>Gió ${compassLabel(p.direction).toLowerCase()}</b>`,
          `Giờ PM2.5 ≥ 115: <b>${p.exceed_pct == null ? '—' : fmtPct(p.exceed_pct)}</b>`,
          `PM2.5 trung bình: <b>${p.pm25_avg == null ? '—' : `${fmtNum(p.pm25_avg)} µg/m³`}</b>`,
          `Gió hướng này: ${fmtPct(total ? (100 * p.hours) / total : 0)} số giờ (${fmtNum(p.hours, 0)} giờ)`,
        ].join('<br/>')
      },
    },
    polar: { radius: [12, '76%'] },
    // Category sectors are centred, so start half a sector (11.25°) past north to put N on top.
    angleAxis: {
      type: 'category',
      data: rose.map((p) => compassLabel(p.direction)),
      startAngle: 90 + 360 / 32,
      clockwise: true,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: INK.axis } },
      // Every other label: the 8 main directions; the in-between ones are in the tooltip.
      axisLabel: { interval: 1, color: INK.secondary, fontSize: 11 },
    },
    // Ring labels run along the N/NNW edge, so they sit above the petals with a halo.
    radiusAxis: {
      type: 'value',
      min: 0,
      splitNumber: 3,
      z: 10,
      axisLabel: {
        formatter: (v: number) => `${fmtNum(v, 0)}%`,
        fontSize: 10,
        showMinLabel: false,
        textBorderColor: INK.surface,
        textBorderWidth: 3,
      },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: INK.grid } },
    },
    series: [
      {
        type: 'bar',
        coordinateSystem: 'polar',
        color: SERIES.blue,
        itemStyle: { borderRadius: 2 },
        emphasis: { itemStyle: { color: SERIES.orange } },
        data: rose.map((p) => p.exceed_pct),
      },
    ],
  }
}

function extremes(rose: WindRosePoint[]) {
  const scored = rose.filter((p): p is WindRosePoint & { exceed_pct: number } => p.exceed_pct != null)
  if (scored.length < 2) return null
  const sorted = [...scored].sort((a, b) => b.exceed_pct - a.exceed_pct)
  return { high: sorted[0], low: sorted[sorted.length - 1] }
}

export function WeatherPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [scatterVar, setScatterVar] = useState<Variable>('relative_humidity_pct_avg')
  const [data, setData] = useState<WeatherResponse | null>(null)
  const [rose, setRose] = useState<WindRoseResponse | null>(null)
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
    const filters = { date_from: dateFrom, date_to: dateTo, station_key: stationKey ? Number(stationKey) : null }
    const request =
      scatterVar === WIND_DIRECTION
        ? fetchWindRose(filters).then((res) => {
            if (!cancelled) setRose(res)
          })
        : fetchWeather({ ...filters, scatter_variable: scatterVar }).then((res) => {
            if (!cancelled) setData(res)
          })
    request
      .then(() => {
        if (!cancelled) setError(null)
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
  const isRose = scatterVar === WIND_DIRECTION
  const shown = !isRose && data && data.scatter_variable === scatterVar ? data : null
  const shownRose = isRose ? rose : null
  const seriesValues = (point: WeatherSeriesPoint) => point[spec.value]
  const days = shown?.series.map((point) => point.date_day) ?? []

  // One tooltip for both panels: the day, PM2.5 and the weather variable, each with its unit.
  const tooltipFor = (params: { dataIndex: number }[]) => {
    const point = shown?.series[params[0]?.dataIndex ?? -1]
    if (!point) return ''
    const fmt = (v: number | null | undefined, unit: string) =>
      v == null ? '—' : `${fmtNum(v)}${unit === '%' ? '' : ' '}${unit}`
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
  const roseEnds = shownRose ? extremes(shownRose.points) : null
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
        description="PM2.5 đi cùng nhiệt độ, độ ẩm, tốc độ và hướng gió, áp suất, mưa và mây như thế nào."
      />

      <FilterBar busy={loading && (shown != null || shownRose != null)}>
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
          onChange={(value) => value && setScatterVar(value as Variable)}
          allowDeselect={false}
          maxDropdownHeight={420}
          w={220}
        />
      </FilterBar>

      {error && <ErrorAlert title="Không tải được dữ liệu thời tiết" message={error} />}
      {!shown && !shownRose && loading && !error && <LoadingBlock height={340} />}

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
            description={`${readCloud(spec.value, shown)}${fit ? ' Đường đứt là xu hướng tuyến tính.' : ''}`}
            busy={loading}
            actions={
              fit &&
              perStep != null && (
                <Group gap="xl" wrap="nowrap">
                  <Metric label="Hệ số tương quan r" value={fmtNum(fit.r, 2)} hint={`${fit.n} ngày`} size="sm" />
                  <Metric
                    label="Độ dốc"
                    value={fmtSigned(perStep)}
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

      {shownRose && !error && (
        <Panel
          title="PM2.5 theo hướng gió"
          description="Mỗi cánh là một trong 16 hướng gió; cánh càng dài thì càng nhiều giờ PM2.5 ≥ 115 µg/m³. Tính theo từng giờ, cùng khoảng ngày và trạm đang chọn."
          busy={loading}
          actions={
            roseEnds && (
              <Group gap="xl" wrap="nowrap">
                <Metric
                  label="Nhiều giờ vượt nhất"
                  value={fmtPct(roseEnds.high.exceed_pct)}
                  hint={`gió ${compassLabel(roseEnds.high.direction).toLowerCase()}`}
                  size="sm"
                />
                <Metric
                  label="Ít nhất"
                  value={fmtPct(roseEnds.low.exceed_pct)}
                  hint={`gió ${compassLabel(roseEnds.low.direction).toLowerCase()}`}
                  size="sm"
                />
              </Group>
            )
          }
        >
          <Chart
            option={windRoseOption(shownRose.points)}
            height={420}
            label="Hoa gió: phần trăm số giờ PM2.5 từ 115 µg/m³ trở lên theo 16 hướng gió."
          />
        </Panel>
      )}
    </Stack>
  )
}
