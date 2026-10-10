import {
  Alert,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useEffect, useState } from 'react'
import { DateStationFilters } from '../components/DateStationFilters'
import { TrendChart } from '../components/TrendChart'
import {
  fetchOverviewKpis,
  fetchOverviewMeta,
  fetchOverviewTrends,
  type OverviewKpis,
  type OverviewMeta,
  type OverviewTrends,
} from '../api/overview'
import { fetchStations, type Station } from '../api/stations'

function fmt(n: number | null | undefined, digits = 1) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(digits)
}

export function OverviewPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [kpis, setKpis] = useState<OverviewKpis | null>(null)
  const [trends, setTrends] = useState<OverviewTrends | null>(null)
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
    const key = stationKey ? Number(stationKey) : null
    Promise.all([
      fetchOverviewKpis({
        date_from: dateFrom,
        date_to: dateTo,
        station_key: key,
      }),
      fetchOverviewTrends({
        date_from: dateFrom,
        date_to: dateTo,
        station_key: key,
      }),
    ])
      .then(([k, t]) => {
        if (!cancelled) {
          setKpis(k)
          setTrends(t)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [dateFrom, dateTo, stationKey])

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Tổng quan</Title>
        <Text size="sm" c="dimmed">
          KPI và xu hướng từ mart_station_daily
          {meta
            ? ` · dữ liệu ${meta.data_min} → ${meta.data_max}`
            : ''}
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

      {error && (
        <Alert color="red" title="Lỗi tải dữ liệu">
          {error}
        </Alert>
      )}

      {loading && (
        <Group>
          <Loader size="sm" />
          <Text size="sm">Đang tải…</Text>
        </Group>
      )}

      {kpis && !loading && (
        <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }} spacing="sm">
          <Paper withBorder p="md" radius="sm">
            <Text size="xs" c="dimmed">
              PM2.5 TB
            </Text>
            <Text fw={600} size="xl">
              {fmt(kpis.pm25_avg)}
            </Text>
            <Text size="xs" c="dimmed">
              µg/m³
            </Text>
          </Paper>
          <Paper withBorder p="md" radius="sm">
            <Text size="xs" c="dimmed">
              PM10 TB
            </Text>
            <Text fw={600} size="xl">
              {fmt(kpis.pm10_avg)}
            </Text>
            <Text size="xs" c="dimmed">
              µg/m³
            </Text>
          </Paper>
          <Paper withBorder p="md" radius="sm">
            <Text size="xs" c="dimmed">
              O3 TB
            </Text>
            <Text fw={600} size="xl">
              {fmt(kpis.o3_avg)}
            </Text>
            <Text size="xs" c="dimmed">
              µg/m³
            </Text>
          </Paper>
          <Paper withBorder p="md" radius="sm">
            <Text size="xs" c="dimmed">
              Ngày×trạm
            </Text>
            <Text fw={600} size="xl">
              {kpis.station_day_rows}
            </Text>
            <Text size="xs" c="dimmed">
              có PM2.5: {kpis.pm25_day_rows}
            </Text>
          </Paper>
          <Paper withBorder p="md" radius="sm">
            <Text size="xs" c="dimmed">
              Số episode
            </Text>
            <Text fw={600} size="xl">
              {kpis.episode_count}
            </Text>
            <Text size="xs" c="dimmed">
              giao khoảng lọc
            </Text>
          </Paper>
        </SimpleGrid>
      )}

      {trends && !loading && (
        <Paper withBorder p="md" radius="sm">
          <Text fw={600} mb="xs">
            Xu hướng theo ngày
            {stationKey ? '' : ' (trung bình 12 trạm)'}
          </Text>
          {trends.points.length === 0 ? (
            <Text size="sm" c="dimmed">
              Không có điểm dữ liệu trong khoảng chọn.
            </Text>
          ) : (
            <TrendChart points={trends.points} />
          )}
        </Paper>
      )}
    </Stack>
  )
}
