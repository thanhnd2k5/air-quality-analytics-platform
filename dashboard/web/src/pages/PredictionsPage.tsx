import { Alert, Select, SimpleGrid, Stack, Table, Text } from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import {
  fetchPredictionMeta,
  fetchPredictions,
  type PredictionMeta,
  type PredictionsResponse,
} from '../api/predictions'
import { fetchStations, type Station } from '../api/stations'
import { Chart } from '../components/Chart'
import { DateStationFilters } from '../components/DateStationFilters'
import { StatCard } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { FilterBar, Panel } from '../components/Panel'
import { Pm25Badge } from '../components/Pm25Badge'
import { EmptyState, ErrorAlert, LoadingBlock } from '../components/States'
import { fmtNum, fmtSigned } from '../format'
import { NEUTRAL_SERIES, SERIES } from '../theme'


/** "2016-12-31T23:00" → "31/12/2016 23:00", as the date pickers show it. */
function fmtTimeVi(iso: string) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)} ${iso.slice(11, 16)}`
}

const SPLIT_LABEL: Record<string, string> = {
  train: 'Giai đoạn học',
  val: 'Giai đoạn tinh chỉnh',
  test: 'Giai đoạn đánh giá',
}

const STAGE_WINDOW: Record<string, { start: string; end: string; label: string }> = {
  train: { start: '2013-03-01', end: '2015-12-31', label: 'Học' },
  val: { start: '2016-01-01', end: '2016-06-30', label: 'Tinh chỉnh' },
  test: { start: '2016-07-01', end: '2016-12-31', label: 'Đánh giá' },
}

function addDays(iso: string, days: number) {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function datesForStage(split: string, dataMin: string, dataMax: string) {
  const stage = STAGE_WINDOW[split]
  if (!stage) return null
  const end = stage.end < dataMax ? stage.end : dataMax
  const floor = stage.start > dataMin ? stage.start : dataMin
  const start = addDays(end, -13)
  return { from: start < floor ? floor : start, to: end }
}

function splitLabel(split: string) {
  return SPLIT_LABEL[split] ?? split
}

/** % by which the model's MAE is below the baseline's (positive = model better). */
function reduction(model: number | null, baseline: number | null) {
  if (model == null || baseline == null || baseline === 0) return null
  return (1 - model / baseline) * 100
}

/** "−7.0%" when the model's error is lower, "+x%" when higher. */
function fmtReduction(r: number | null) {
  return r == null ? '—' : `${fmtSigned(-r)}%`
}

function pickHeadline(metrics: PredictionsResponse['metrics']) {
  return metrics.find((m) => m.split === 'test') ?? metrics[0] ?? null
}

export function PredictionsPage() {
  const [meta, setMeta] = useState<PredictionMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [split, setSplit] = useState<string | null>('test')
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

  const series = data?.series ?? []
  const latest = series.length ? series[series.length - 1] : null
  const headline = data ? pickHeadline(data.metrics) : null

  const chartOption = {
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number | string) =>
        v == null || v === '' ? '—' : `${fmtNum(Number(v))} µg/m³`,
    },
    legend: {
      data: ['Dự báo của mô hình', 'Thực tế đo được', 'Cách đơn giản (giờ trước)'],
      // The three lines nearly coincide; the baseline starts hidden (click the legend to show it).
      selected: { 'Cách đơn giản (giờ trước)': false },
    },
    grid: { left: 8, right: 16, top: 48, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      // Categories are already "DD/MM/YYYY HH:MM", so the tooltip header reads like the date pickers.
      data: series.map((p) => fmtTimeVi(p.target_time)),
      axisLabel: { formatter: (t: string) => `${t.slice(0, 5)} ${t.slice(11, 13)}h` },
    },
    yAxis: { type: 'value', name: 'PM2.5 (µg/m³)' },
    series: [
      {
        name: 'Dự báo của mô hình',
        type: 'line',
        showSymbol: false,
        color: SERIES.blue,
        z: 3,
        data: series.map((p) => p.predicted_pm25),
      },
      {
        name: 'Thực tế đo được',
        type: 'line',
        showSymbol: false,
        color: NEUTRAL_SERIES.strong,
        lineStyle: { width: 1.5 },
        data: series.map((p) => p.actual_pm25),
      },
      {
        name: 'Cách đơn giản (giờ trước)',
        type: 'line',
        showSymbol: false,
        color: NEUTRAL_SERIES.soft,
        lineStyle: { type: 'dashed', width: 1.5 },
        data: series.map((p) => p.predicted_pm25_persistence),
      },
    ],
  }

  const stationName =
    stationKey != null
      ? stations.find((s) => String(s.station_key) === stationKey)?.station_name
      : null

  return (
    <Stack gap="lg">
      <PageHeader
        title="Dự báo PM2.5 giờ tới"
        description="Số PM2.5 mô hình hồi quy đoán cho từng giờ, đặt cạnh số đo thật và cách lấy nguyên giờ trước."
      />

      <FilterBar busy={loading && data != null}>
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
          label="Giai đoạn"
          clearable
          placeholder="Tất cả"
          data={[
            { value: 'test', label: 'Đánh giá' },
            { value: 'val', label: 'Tinh chỉnh' },
            { value: 'train', label: 'Học' },
          ]}
          value={split}
          onChange={(value) => {
            setSplit(value)
            if (!value || !meta) return
            const window = datesForStage(value, meta.data_min, meta.data_max)
            if (!window) return
            setDateFrom(window.from)
            setDateTo(window.to)
          }}
          w={180}
        />
      </FilterBar>

      {error && <ErrorAlert title="Không tải được dự báo" message={error} />}
      {!data && loading && !error && <LoadingBlock height={360} />}

      {data && !error && (
        <>
          {latest ? (
            <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
              <StatCard
                label="Dự báo gần nhất"
                value={fmtNum(latest.predicted_pm25)}
                unit="µg/m³"
                hint={`${fmtTimeVi(latest.target_time)} · ${stationName ?? 'trung bình các trạm'}`}
              >
                {latest.predicted_pm25 != null && <Pm25Badge value={latest.predicted_pm25} />}
              </StatCard>
              <StatCard label="Thực tế đo được" value={fmtNum(latest.actual_pm25)} unit="µg/m³" />
              <StatCard
                label="Lệch giữa dự báo và thực tế"
                value={fmtNum(latest.absolute_error)}
                unit="µg/m³"
              />
            </SimpleGrid>
          ) : (
            <Alert color="yellow" title="Chưa có điểm dự báo" icon={<IconInfoCircle size={18} />}>
              {split && STAGE_WINDOW[split]
                ? `Giai đoạn ${STAGE_WINDOW[split].label} chỉ có giờ từ ${STAGE_WINDOW[split].start} đến ${STAGE_WINDOW[split].end}. Khoảng ngày đang chọn nằm ngoài giai đoạn này.`
                : 'Không có dữ liệu trong khoảng đã chọn. Thử đổi ngày hoặc trạm.'}
            </Alert>
          )}

          <Panel title="Dự báo theo thời gian" busy={loading}>
            {series.length === 0 ? (
              <EmptyState title="Không có chuỗi để vẽ" description="Thử đổi khoảng ngày, trạm hoặc giai đoạn." />
            ) : (
              <Chart
                option={chartOption}
                height={380}
                label="PM2.5 dự báo của mô hình, số đo thực tế và cách lấy nguyên giờ trước, theo giờ."
              />
            )}
          </Panel>

          <Panel
            title="Sai số tuyệt đối trung bình (MAE)"
            description={
              headline && headline.mae_model != null ? (
                <>
                  Trung bình mỗi giờ lệch khoảng <strong>{fmtNum(headline.mae_model)} µg/m³</strong>
                  {headline.mae_persistence != null
                    ? `, so với ${fmtNum(headline.mae_persistence)} µg/m³ của cách đơn giản (giảm ${fmtNum(reduction(headline.mae_model, headline.mae_persistence))}%).`
                    : '.'}
                </>
              ) : undefined
            }
            busy={loading}
          >
            <Table.ScrollContainer minWidth={480}>
              <Table highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Giai đoạn</Table.Th>
                    <Table.Th ta="right">Số điểm giờ</Table.Th>
                    <Table.Th ta="right">Sai số mô hình</Table.Th>
                    <Table.Th ta="right">Sai số cách đơn giản</Table.Th>
                    <Table.Th ta="right">So với cách đơn giản</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.metrics.map((m) => (
                    <Table.Tr key={m.split}>
                      <Table.Td>{splitLabel(m.split)}</Table.Td>
                      <Table.Td ta="right">{fmtNum(m.n, 0)}</Table.Td>
                      <Table.Td ta="right" fw={600}>
                        {fmtNum(m.mae_model)}{' '}
                        <Text span size="xs" c="dimmed" fw={400}>
                          µg/m³
                        </Text>
                      </Table.Td>
                      <Table.Td ta="right">
                        {fmtNum(m.mae_persistence)}{' '}
                        <Text span size="xs" c="dimmed">
                          µg/m³
                        </Text>
                      </Table.Td>
                      <Table.Td ta="right" fw={600}>
                        {fmtReduction(reduction(m.mae_model, m.mae_persistence))}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </Panel>
        </>
      )}
    </Stack>
  )
}
