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
  Title,
} from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useMemo, useState } from 'react'
import {
  fetchPredictionMeta,
  fetchPredictions,
  type PredictionMeta,
  type PredictionsResponse,
} from '../api/predictions'
import { fetchStations, type Station } from '../api/stations'
import { DateStationFilters } from '../components/DateStationFilters'

function fmt(n: number | null | undefined, d = 1) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(d)
}

function fmtTime(iso: string) {
  return iso.replace('T', ' ').slice(0, 16)
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

function pickHeadline(metrics: PredictionsResponse['metrics']) {
  return metrics.find((m) => m.split === 'test') ?? metrics[0] ?? null
}

function aqiHint(pm25: number | null | undefined): string {
  if (pm25 == null) return ''
  if (pm25 <= 35) return 'Mức thấp'
  if (pm25 <= 75) return 'Mức trung bình'
  if (pm25 <= 115) return 'Hơi cao'
  if (pm25 <= 150) return 'Cao'
  return 'Rất cao'
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

  const recentRows = useMemo(() => {
    if (!series.length) return []
    return [...series].slice(-12).reverse()
  }, [series])

  const chartOption = {
    color: ['#0d9488', '#334155', '#94a3b8'],
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number | string) =>
        v == null || v === '' ? '—' : `${Number(v).toFixed(1)} µg/m³`,
    },
    legend: {
      top: 0,
      data: ['Dự báo của mô hình', 'Thực tế đo được', 'Cách đơn giản (giờ trước)'],
    },
    grid: { left: 56, right: 24, top: 48, bottom: 40 },
    xAxis: {
      type: 'category',
      data: series.map((p) => fmtTime(p.target_time)),
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: 'PM2.5 (µg/m³)',
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
    },
    series: [
      {
        name: 'Dự báo của mô hình',
        type: 'line',
        showSymbol: false,
        lineStyle: { width: 2.5 },
        data: series.map((p) => p.predicted_pm25),
      },
      {
        name: 'Thực tế đo được',
        type: 'line',
        showSymbol: false,
        data: series.map((p) => p.actual_pm25),
      },
      {
        name: 'Cách đơn giản (giờ trước)',
        type: 'line',
        showSymbol: false,
        lineStyle: { type: 'dashed' },
        data: series.map((p) => p.predicted_pm25_persistence),
      },
    ],
  }

  const stationName =
    stationKey != null
      ? stations.find((s) => String(s.station_key) === stationKey)?.station_name
      : null

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Dự báo PM2.5 giờ tới</Title>
        <Text size="sm" c="dimmed" maw={720}>
          Đây là số PM2.5 mô hình đã đoán cho từng giờ (trước khi biết kết quả đo).
          Phần sai số chỉ để xem dự báo có sát thực tế không — không phải nội dung chính.
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
          label="Xem giai đoạn"
          clearable
          placeholder="Tất cả"
          data={[
            { value: 'test', label: 'Đánh giá (khuyên dùng)' },
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
          w={200}
        />
      </Group>
      <Text size="xs" c="dimmed">
        Đổi giai đoạn sẽ đưa ngày về 14 ngày cuối của giai đoạn đó. Học đến 31/12/2015, tinh chỉnh đến 30/06/2016, đánh giá đến 31/12/2016.
      </Text>

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
          {latest ? (
            <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
              <Paper withBorder p="md" radius="sm">
                <Text size="xs" c="dimmed" tt="uppercase">
                  Dự báo gần nhất
                </Text>
                <Text fw={700} size="2rem" mt={4}>
                  {fmt(latest.predicted_pm25)}{' '}
                  <Text span size="sm" fw={500} c="dimmed">
                    µg/m³
                  </Text>
                </Text>
                <Text size="sm" c="dimmed">
                  {fmtTime(latest.target_time)}
                  {stationName ? ` · ${stationName}` : ' · trung bình các trạm'}
                </Text>
                {latest.predicted_pm25 != null && (
                  <Badge mt={8} variant="light" color="teal">
                    {aqiHint(latest.predicted_pm25)}
                  </Badge>
                )}
              </Paper>
              <Paper withBorder p="md" radius="sm">
                <Text size="xs" c="dimmed" tt="uppercase">
                  Thực tế đo được
                </Text>
                <Text fw={700} size="2rem" mt={4}>
                  {fmt(latest.actual_pm25)}{' '}
                  <Text span size="sm" fw={500} c="dimmed">
                    µg/m³
                  </Text>
                </Text>
                <Text size="sm" c="dimmed">
                  Cùng giờ đó máy quan trắc ghi nhận
                </Text>
              </Paper>
              <Paper withBorder p="md" radius="sm">
                <Text size="xs" c="dimmed" tt="uppercase">
                  Lệch bao nhiêu?
                </Text>
                <Text fw={700} size="2rem" mt={4}>
                  {fmt(latest.absolute_error)}{' '}
                  <Text span size="sm" fw={500} c="dimmed">
                    µg/m³
                  </Text>
                </Text>
                <Text size="sm" c="dimmed">
                  |dự báo − thực tế| ở giờ gần nhất
                </Text>
              </Paper>
            </SimpleGrid>
          ) : (
            <Alert color="yellow" title="Chưa có điểm dự báo">
              {split && STAGE_WINDOW[split]
                ? `Giai đoạn ${STAGE_WINDOW[split].label} chỉ có giờ từ ${STAGE_WINDOW[split].start} đến ${STAGE_WINDOW[split].end}. Khoảng ngày đang chọn nằm ngoài giai đoạn này.`
                : 'Không có dữ liệu trong khoảng đã chọn. Thử đổi ngày hoặc trạm.'}
            </Alert>
          )}

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb={4}>
              Số dự báo theo thời gian
            </Text>
            <Text size="sm" c="dimmed" mb="sm">
              Đường xanh là số mô hình đoán. Đường đậm là thực tế. Càng sát nhau càng tốt.
              {!stationKey
                ? ' Đang lấy trung bình mọi trạm — chọn 1 trạm để xem rõ hơn.'
                : null}
            </Text>
            {series.length === 0 ? (
              <Text size="sm" c="dimmed">
                Không có chuỗi để vẽ.
              </Text>
            ) : (
              <ReactECharts option={chartOption} style={{ height: 380 }} />
            )}
          </Paper>

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb={4}>
              12 giờ gần nhất trong khoảng chọn
            </Text>
            <Text size="sm" c="dimmed" mb="sm">
              Cột chính là <strong>số dự báo</strong>; thực tế và lệch để đối chiếu.
            </Text>
            {recentRows.length === 0 ? (
              <Text size="sm" c="dimmed">
                Không có dòng nào.
              </Text>
            ) : (
              <Table striped withTableBorder>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Thời điểm</Table.Th>
                    <Table.Th>Dự báo</Table.Th>
                    <Table.Th>Thực tế</Table.Th>
                    <Table.Th>Lệch</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {recentRows.map((p) => (
                    <Table.Tr key={p.target_time}>
                      <Table.Td>{fmtTime(p.target_time)}</Table.Td>
                      <Table.Td>
                        <Text fw={600}>{fmt(p.predicted_pm25)} µg/m³</Text>
                        <Text size="xs" c="dimmed">
                          {aqiHint(p.predicted_pm25)}
                        </Text>
                      </Table.Td>
                      <Table.Td>{fmt(p.actual_pm25)} µg/m³</Table.Td>
                      <Table.Td>{fmt(p.absolute_error)} µg/m³</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Paper>

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb={4}>
              Độ tin cậy (phụ)
            </Text>
            <Text size="sm" c="dimmed" mb="sm">
              Sai số trung bình trên cả khoảng lọc — dùng để biết mô hình có đáng tin không,
              không thay cho số dự báo từng giờ ở trên.
            </Text>
            {headline && headline.mae_model != null && (
              <Text size="sm" mb="sm">
                Trung bình mỗi giờ lệch khoảng <strong>{fmt(headline.mae_model)} µg/m³</strong>
                {headline.mae_persistence != null
                  ? ` (cách đơn giản: ${fmt(headline.mae_persistence)} µg/m³)`
                  : ''}
                .
              </Text>
            )}
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Giai đoạn</Table.Th>
                  <Table.Th>Số điểm giờ</Table.Th>
                  <Table.Th>Sai số mô hình</Table.Th>
                  <Table.Th>Sai số cách đơn giản</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.metrics.map((m) => (
                  <Table.Tr key={m.split}>
                    <Table.Td>{splitLabel(m.split)}</Table.Td>
                    <Table.Td>{m.n.toLocaleString('vi-VN')}</Table.Td>
                    <Table.Td>{fmt(m.mae_model)} µg/m³</Table.Td>
                    <Table.Td>{fmt(m.mae_persistence)} µg/m³</Table.Td>
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
