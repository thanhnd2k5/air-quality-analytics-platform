import {
  Alert,
  Box,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { useEffect, useState } from 'react'
import { fetchStationCompare, type StationCompareRow } from '../api/compare'
import {
  fetchOverviewKpis,
  fetchOverviewMeta,
  fetchOverviewTrends,
  type OverviewKpis,
  type OverviewMeta,
  type OverviewTrends,
} from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import { DateStationFilters } from '../components/DateStationFilters'
import { TrendChart } from '../components/TrendChart'

function fmt(n: number | null | undefined, digits = 1) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(digits)
}

function fmtDate(iso: string) {
  const [year, month, day] = iso.slice(0, 10).split('-')
  if (!year || !month || !day) return iso
  return `${day}/${month}/${year}`
}

function count(n: number) {
  return n.toLocaleString('vi-VN')
}

function scopeSentence(kpis: OverviewKpis, stationName: string | null) {
  const who = stationName ? `trạm ${stationName}` : 'trung bình 12 trạm'
  return `Từ ${fmtDate(kpis.date_from)} đến ${fmtDate(kpis.date_to)}, ${who}.`
}

function pm25Tone(value: number | null) {
  if (value == null) return { name: 'gray', label: 'Chưa có số', text: 'gray.7' }
  if (value <= 35) return { name: 'teal', label: 'Thấp', text: 'teal.8' }
  if (value <= 75) return { name: 'yellow', label: 'Trung bình', text: 'yellow.8' }
  if (value <= 115) return { name: 'orange', label: 'Hơi cao', text: 'orange.8' }
  if (value <= 150) return { name: 'red', label: 'Cao', text: 'red.7' }
  return { name: 'red', label: 'Rất cao', text: 'red.9' }
}

function Figure({
  label,
  value,
  unit,
  color,
}: {
  label: string
  value: string
  unit: string
  color?: string
}) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Group gap={6} align="baseline" wrap="nowrap">
        <Text
          fw={700}
          fz={28}
          lh={1}
          c={color}
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          {value}
        </Text>
        {unit && (
          <Text size="sm" c="dimmed">
            {unit}
          </Text>
        )}
      </Group>
    </Stack>
  )
}

function LevelBar({
  label,
  row,
  max,
}: {
  label: string
  row: StationCompareRow
  max: number
}) {
  const tone = pm25Tone(row.pm25_avg)
  const width =
    row.pm25_avg == null || max <= 0 ? 0 : Math.max(6, (row.pm25_avg / max) * 100)
  const place = row.district ? `${row.station_name} · ${row.district}` : row.station_name
  return (
    <Stack gap={6}>
      <Group justify="space-between" wrap="nowrap">
        <Text size="sm" c="dimmed">
          {label}
        </Text>
        <Text size="sm" fw={700}>
          {fmt(row.pm25_avg)} µg/m³
        </Text>
      </Group>
      <Box h={10} bg="gray.1" style={{ borderRadius: 99, overflow: 'hidden' }}>
        <Box
          h="100%"
          bg={tone.text}
          style={{ width: `${width}%`, borderRadius: 99 }}
        />
      </Box>
      <Text size="sm">{place}</Text>
    </Stack>
  )
}

function OverviewBody({
  kpis,
  stationName,
}: {
  kpis: OverviewKpis
  stationName: string | null
}) {
  const wide = useMediaQuery('(min-width: 62em)')
  const tone = pm25Tone(kpis.pm25_avg)
  const coverage =
    kpis.pm25_day_rows === 0
      ? 'Khoảng này không có số PM2.5.'
      : stationName
        ? `${count(kpis.pm25_day_rows)} ngày có số`
        : `${count(kpis.pm25_day_rows)} ngày quan trắc trên 12 trạm`
  const accent = `var(--mantine-color-${tone.name}-6)`
  const line = '1px solid var(--mantine-color-gray-2)'
  const figures = [
    {
      label: 'Từ 115 µg/m³',
      value: count(kpis.days_pm25_ge_115),
      unit: 'ngày',
      color: 'orange.8',
    },
    {
      label: 'Số đợt',
      value: count(kpis.episode_count),
      unit: 'đợt',
      color: 'red.7',
    },
    {
      label: 'Đợt trung bình',
      value: kpis.duration_hours_avg == null ? '—' : fmt(kpis.duration_hours_avg, 1),
      unit: kpis.duration_hours_avg == null ? '' : 'giờ',
      color: 'dark.7',
    },
    {
      label: 'Đợt dài nhất',
      value: kpis.duration_hours_max == null ? '—' : count(kpis.duration_hours_max),
      unit: kpis.duration_hours_max == null ? '' : 'giờ',
      color: 'dark.7',
    },
  ]
  if (!stationName && kpis.multi_station_event_count != null) {
    figures.push({
      label: 'Ít nhất 6 trạm',
      value: count(kpis.multi_station_event_count),
      unit: 'lần',
      color: 'teal.8',
    })
  }
  const pollutants = [
    ['PM10', kpis.pm10_avg],
    ['O3', kpis.o3_avg],
    ['SO2', kpis.so2_avg],
    ['NO2', kpis.no2_avg],
    ['CO', kpis.co_avg],
  ] as const

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {scopeSentence(kpis, stationName)}
      </Text>

      <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
        <Box
          style={{
            display: 'grid',
            gridTemplateColumns: wide ? 'minmax(240px, 0.85fr) 1.3fr' : '1fr',
          }}
        >
          <Box
            px="xl"
            py="lg"
            style={{
              boxShadow: wide ? `inset 4px 0 0 ${accent}` : `inset 0 4px 0 ${accent}`,
            }}
          >
            <Group gap="sm" align="baseline">
              <Text size="sm" fw={700}>
                PM2.5 TB
              </Text>
              <Text size="sm" fw={700} c={tone.text}>
                {tone.label}
              </Text>
            </Group>
            <Group align="baseline" gap={8} mt={6}>
              <Text
                fz={{ base: 52, sm: 60 }}
                fw={700}
                lh={1}
                c={tone.text}
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                {fmt(kpis.pm25_avg)}
              </Text>
              <Text size="md" c="dimmed">
                µg/m³
              </Text>
            </Group>
            <Text size="sm" c="dimmed" mt="sm">
              {coverage}
            </Text>
          </Box>
          <Box
            px="xl"
            py="lg"
            style={{
              borderLeft: wide ? line : undefined,
              borderTop: wide ? undefined : line,
            }}
          >
            <Text size="xs" c="dimmed" mb="md">
              Cùng khoảng, trung bình theo ngày
            </Text>
            <SimpleGrid cols={wide ? 5 : 2} spacing="lg">
              {pollutants.map(([label, value]) => (
                <Figure key={label} label={label} value={fmt(value)} unit="µg/m³" />
              ))}
            </SimpleGrid>
          </Box>
        </Box>
      </Paper>

      <Paper withBorder radius="md" px="md" py="lg">
        <SimpleGrid cols={{ base: 2, sm: figures.length }} spacing="lg">
          {figures.map((figure) => (
            <Figure key={figure.label} {...figure} />
          ))}
        </SimpleGrid>
        <Text size="xs" c="dimmed" mt="md">
          Một đợt là ít nhất 3 giờ liên tiếp có PM2.5 từ 115 µg/m³.
        </Text>
      </Paper>
    </Stack>
  )
}

function StationSpread({
  highest,
  lowest,
}: {
  highest: StationCompareRow
  lowest: StationCompareRow
}) {
  const max = Math.max(highest.pm25_avg ?? 0, lowest.pm25_avg ?? 0, 1)
  return (
    <Paper withBorder p="md" radius="md">
      <Text fw={600} mb="md">
        PM2.5 TB giữa các trạm
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl">
        <LevelBar label="Cao nhất" row={highest} max={max} />
        <LevelBar label="Thấp nhất" row={lowest} max={max} />
      </SimpleGrid>
    </Paper>
  )
}

function TrendPanel({
  stationName,
  trends,
}: {
  stationName: string | null
  trends: OverviewTrends
}) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text fw={600}>Xu hướng theo ngày</Text>
      <Text size="sm" c="dimmed" mb="xs">
        {stationName ?? '12 trạm'}. Vạch đỏ là mốc 115 µg/m³ theo giờ, dùng để đếm đợt.
      </Text>
      {trends.points.length === 0 ? (
        <Text size="sm" c="dimmed">
          Không có điểm dữ liệu trong khoảng chọn.
        </Text>
      ) : (
        <TrendChart points={trends.points} height={360} />
      )}
    </Paper>
  )
}

export function OverviewPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [stationKey, setStationKey] = useState<string | null>(null)
  const [kpis, setKpis] = useState<OverviewKpis | null>(null)
  const [trends, setTrends] = useState<OverviewTrends | null>(null)
  const [compareRows, setCompareRows] = useState<StationCompareRow[]>([])
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
    const kpisPromise = fetchOverviewKpis({
      date_from: dateFrom,
      date_to: dateTo,
      station_key: key,
    })
    const trendsPromise = fetchOverviewTrends({
      date_from: dateFrom,
      date_to: dateTo,
      station_key: key,
    })
    const comparePromise =
      key == null
        ? fetchStationCompare({ date_from: dateFrom, date_to: dateTo })
        : Promise.resolve(null)

    Promise.all([kpisPromise, trendsPromise, comparePromise])
      .then(([k, t, c]) => {
        if (!cancelled) {
          setKpis(k)
          setTrends(t)
          setCompareRows(c ? c.rows : [])
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

  const stationName =
    stations.find((s) => String(s.station_key) === stationKey)?.station_name ?? null
  const ranked = [...compareRows].sort(
    (a, b) => a.rank_pm25 - b.rank_pm25 || a.station_name.localeCompare(b.station_name),
  )
  const highest = ranked[0]
  const lowest = ranked.length > 1 ? ranked[ranked.length - 1] : undefined

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Tổng quan</Title>
        <Text size="sm" c="dimmed">
          {meta
            ? `Kho dữ liệu có từ ${fmtDate(meta.data_min)} đến ${fmtDate(meta.data_max)}.`
            : 'Mức trung bình và xu hướng theo ngày.'}
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

      {kpis && !loading && <OverviewBody kpis={kpis} stationName={stationName} />}

      {kpis && !loading && !stationKey && highest && lowest && (
        <StationSpread highest={highest} lowest={lowest} />
      )}

      {trends && !loading && <TrendPanel stationName={stationName} trends={trends} />}
    </Stack>
  )
}
