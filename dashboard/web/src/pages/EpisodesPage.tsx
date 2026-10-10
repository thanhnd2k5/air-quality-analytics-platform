import {
  Alert,
  Group,
  Loader,
  Paper,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useState } from 'react'
import {
  fetchEpisodes,
  type EpisodeRow,
  type EpisodeSummaryRow,
  type MultiStationEventRow,
} from '../api/episodes'
import { fetchOverviewMeta, type OverviewMeta } from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import { DateStationFilters } from '../components/DateStationFilters'

function fmt(n: number | null | undefined, d = 1) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(d)
}

function fmtDt(s: string) {
  return s.replace('T', ' ').slice(0, 16)
}

export function EpisodesPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [summary, setSummary] = useState<EpisodeSummaryRow[]>([])
  const [episodes, setEpisodes] = useState<EpisodeRow[]>([])
  const [multi, setMulti] = useState<MultiStationEventRow[]>([])
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
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
  }, [])

  useEffect(() => {
    if (!dateFrom || !dateTo) return
    let cancelled = false
    setLoading(true)
    fetchEpisodes({
      date_from: dateFrom,
      date_to: dateTo,
      station_key: stationKey ? Number(stationKey) : null,
    })
      .then((res) => {
        if (!cancelled) {
          setSummary(res.summary)
          setEpisodes(res.episodes)
          setMulti(res.multi_station_events)
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
  }, [dateFrom, dateTo, stationKey])

  const barOption = {
    color: ['#0d9488'],
    tooltip: { trigger: 'axis' },
    grid: { left: 100, right: 24, top: 24, bottom: 40 },
    xAxis: { type: 'value', name: 'Số episode' },
    yAxis: {
      type: 'category',
      data: summary.map((s) => s.station_name).reverse(),
    },
    series: [
      {
        type: 'bar',
        data: summary.map((s) => s.episode_count).reverse(),
      },
    ],
  }

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Đợt ô nhiễm</Title>
        <Text size="sm" c="dimmed">
          Episode PM2.5 ≥ 115 µg/m³, ≥ 3 giờ · sự kiện đa-trạm K=6
        </Text>
      </div>

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

      {!loading && !error && (
        <>
          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Số episode theo trạm
            </Text>
            {summary.length === 0 ? (
              <Text size="sm" c="dimmed">
                Không có episode trong khoảng chọn.
              </Text>
            ) : (
              <ReactECharts
                option={barOption}
                style={{ height: Math.max(280, summary.length * 28) }}
              />
            )}
          </Paper>

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Episode gần đây (tối đa 200)
            </Text>
            <Table striped highlightOnHover withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Trạm</Table.Th>
                  <Table.Th>Bắt đầu</Table.Th>
                  <Table.Th>Kết thúc</Table.Th>
                  <Table.Th>Giờ</Table.Th>
                  <Table.Th>PM2.5 TB</Table.Th>
                  <Table.Th>PM2.5 max</Table.Th>
                  <Table.Th>Temp</Table.Th>
                  <Table.Th>RH%</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {episodes.map((e) => (
                  <Table.Tr key={e.episode_id}>
                    <Table.Td>{e.station_name}</Table.Td>
                    <Table.Td>{fmtDt(e.start_time)}</Table.Td>
                    <Table.Td>{fmtDt(e.end_time)}</Table.Td>
                    <Table.Td>{e.duration_hours}</Table.Td>
                    <Table.Td>{fmt(e.pm25_mean)}</Table.Td>
                    <Table.Td>{fmt(e.pm25_max)}</Table.Td>
                    <Table.Td>{fmt(e.temperature_c_avg)}</Table.Td>
                    <Table.Td>{fmt(e.relative_humidity_pct_avg, 0)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>

          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Sự kiện đa-trạm
            </Text>
            <Table striped highlightOnHover withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Bắt đầu</Table.Th>
                  <Table.Th>Kết thúc</Table.Th>
                  <Table.Th>Giờ</Table.Th>
                  <Table.Th>Peak trạm</Table.Th>
                  <Table.Th>Mean trạm</Table.Th>
                  <Table.Th>K</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {multi.map((m) => (
                  <Table.Tr key={m.event_id}>
                    <Table.Td>{fmtDt(m.start_time)}</Table.Td>
                    <Table.Td>{fmtDt(m.end_time)}</Table.Td>
                    <Table.Td>{m.duration_hours}</Table.Td>
                    <Table.Td>{m.peak_station_count}</Table.Td>
                    <Table.Td>{fmt(m.mean_station_count)}</Table.Td>
                    <Table.Td>{m.multi_station_k}</Table.Td>
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
