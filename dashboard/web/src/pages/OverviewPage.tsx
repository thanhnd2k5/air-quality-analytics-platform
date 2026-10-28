import { Box, Group, Paper, SimpleGrid, Stack, Text } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { useEffect, useMemo, useState } from 'react'
import { fetchStationCompare, type StationCompareRow } from '../api/compare'
import {
  fetchOverviewKpis,
  fetchOverviewMeta,
  fetchOverviewTrends,
  type OverviewKpis,
  type OverviewMeta,
  type OverviewTrends,
  type TrendPoint,
} from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import { Chart } from '../components/Chart'
import { DateStationFilters } from '../components/DateStationFilters'
import { Metric } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { FilterBar, Panel } from '../components/Panel'
import { Dot, Pm25Badge } from '../components/Pm25Badge'
import { EmptyState, ErrorAlert, LoadingBlock } from '../components/States'
import { TrendChart } from '../components/TrendChart'
import { fmtNum, fmtPct } from '../format'
import { CLUSTER, INK, PM25_LEVELS, clusterInfo, pm25Level } from '../theme'

function fmtDate(iso: string) {
  const [year, month, day] = iso.slice(0, 10).split('-')
  if (!year || !month || !day) return iso
  return `${day}/${month}/${year}`
}

function count(n: number) {
  return fmtNum(n, 0)
}

/** All 12 stations ranked by mean PM2.5 over the period, coloured by cluster. */
function StationRanking({ rows }: { rows: StationCompareRow[] }) {
  const sorted = useMemo(
    () => rows.filter((r) => r.pm25_avg != null).sort((a, b) => (b.pm25_avg ?? 0) - (a.pm25_avg ?? 0)),
    [rows],
  )
  const option = useMemo(
    () => ({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: { dataIndex: number }[]) => {
          const r = sorted[params[0]?.dataIndex ?? -1]
          if (!r) return ''
          return [
            `<b>${r.station_name}</b>${r.district ? ` · ${r.district}` : ''}`,
            `PM2.5 trung bình: <b>${fmtNum(r.pm25_avg)} µg/m³</b> (${pm25Level(r.pm25_avg).label.toLowerCase()})`,
            `Số đợt ô nhiễm: <b>${r.episode_count}</b>`,
            `Nhóm: ${clusterInfo(r.cluster_label).label}`,
          ].join('<br/>')
        },
      },
      grid: { left: 8, right: 40, top: 8, bottom: 24, containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        inverse: true,
        data: sorted.map((r) => r.station_name),
        axisLine: { show: false },
        axisLabel: { color: INK.secondary },
      },
      series: [
        {
          type: 'bar',
          barWidth: 14,
          data: sorted.map((r) => ({
            value: Number((r.pm25_avg ?? 0).toFixed(1)),
            itemStyle: { color: clusterInfo(r.cluster_label).color, borderRadius: [0, 4, 4, 0] },
          })),
          label: {
            show: true,
            position: 'right',
            color: INK.secondary,
            fontSize: 11,
            formatter: (p: { value: number }) => fmtNum(p.value),
          },
        },
      ],
    }),
    [sorted],
  )
  return (
    <>
      <Chart option={option} height={340} label="Xếp hạng 12 trạm theo PM2.5 trung bình, tô màu theo nhóm phân cụm." />
      <Group gap="md" mt="xs">
        {Object.values(CLUSTER).map((c) => (
          <Group key={c.label} gap={6} wrap="nowrap">
            <Dot color={c.color} size={10} />
            <Text size="xs">{c.label}</Text>
          </Group>
        ))}
      </Group>
    </>
  )
}

/** How many days fall in each PM2.5 band (daily means), in the band colours. */
function LevelDays({ points }: { points: TrendPoint[] }) {
  const option = useMemo(() => {
    const values = points.map((p) => p.pm25_ug_m3_avg).filter((v): v is number => v != null)
    const counts = PM25_LEVELS.map(({ level }) => values.filter((v) => pm25Level(v).key === level.key).length)
    const total = values.length || 1
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0]?.dataIndex ?? -1
          const band = PM25_LEVELS[i]
          if (!band) return ''
          return `<b>${band.level.label}</b> (${band.range} µg/m³)<br/><b>${counts[i]} ngày</b> · ${fmtPct((counts[i] / total) * 100, 0)} số ngày`
        },
      },
      grid: { left: 8, right: 8, top: 32, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: PM25_LEVELS.map(({ level, range }) => `${level.label}\n${range}`),
        // Only five bands: always show every label (the theme hides "overlapping" ones on phones).
        axisLabel: { lineHeight: 15, interval: 0, hideOverlap: false },
      },
      yAxis: { type: 'value', name: 'ngày', minInterval: 1 },
      series: [
        {
          type: 'bar',
          barWidth: '56%',
          data: counts.map((n, i) => ({ value: n, itemStyle: { color: PM25_LEVELS[i].level.color } })),
          label: { show: true, position: 'top', color: INK.secondary, fontSize: 11 },
        },
      ],
    }
  }, [points])
  return <Chart option={option} height={340} label="Số ngày theo mức PM2.5 trung bình ngày: thấp, trung bình, hơi cao, cao, rất cao." />
}

function OverviewBody({
  kpis,
  stationName,
}: {
  kpis: OverviewKpis
  stationName: string | null
}) {
  const wide = useMediaQuery('(min-width: 62em)')
  const level = pm25Level(kpis.pm25_avg)
  const coverage =
    kpis.pm25_day_rows === 0
      ? 'Khoảng này không có số PM2.5.'
      : stationName
        ? `${count(kpis.pm25_day_rows)} ngày có số tại trạm ${stationName}`
        : `${count(kpis.pm25_day_rows)} ngày quan trắc trên 12 trạm`
  const line = '1px solid var(--mantine-color-gray-3)'
  const figures = [
    { label: 'Ngày từ 115 µg/m³', value: count(kpis.days_pm25_ge_115), unit: 'ngày' },
    { label: 'Số đợt', value: count(kpis.episode_count), unit: 'đợt' },
    {
      label: 'Đợt trung bình',
      value: kpis.duration_hours_avg == null ? '—' : fmtNum(kpis.duration_hours_avg, 1),
      unit: kpis.duration_hours_avg == null ? '' : 'giờ',
    },
    {
      label: 'Đợt dài nhất',
      value: kpis.duration_hours_max == null ? '—' : count(kpis.duration_hours_max),
      unit: kpis.duration_hours_max == null ? '' : 'giờ',
    },
  ]
  if (!stationName && kpis.multi_station_event_count != null) {
    figures.push({
      label: 'Cùng lúc ít nhất 6 trạm',
      value: count(kpis.multi_station_event_count),
      unit: 'lần',
    })
  }
  const pollutants = [
    ['PM10', kpis.pm10_avg],
    ['O₃', kpis.o3_avg],
    ['SO₂', kpis.so2_avg],
    ['NO₂', kpis.no2_avg],
    ['CO', kpis.co_avg],
  ] as const

  return (
    <Stack gap="md">
      <Paper withBorder style={{ overflow: 'hidden' }}>
        <Box
          style={{
            display: 'grid',
            gridTemplateColumns: wide ? 'minmax(260px, 0.8fr) 1.4fr' : '1fr',
          }}
        >
          <Box
            p="lg"
            style={{
              boxShadow: wide ? `inset 3px 0 0 ${level.color}` : `inset 0 3px 0 ${level.color}`,
            }}
          >
            <Group gap="sm" justify="space-between" wrap="nowrap">
              <Text size="sm" fw={600}>
                PM2.5 trung bình
              </Text>
              <Pm25Badge value={kpis.pm25_avg} />
            </Group>
            <Group align="baseline" gap={8} mt="sm" wrap="nowrap">
              <Text fz={{ base: 44, sm: 52 }} fw={650} lh={1} className="tabular">
                {fmtNum(kpis.pm25_avg)}
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
            p="lg"
            style={{
              borderLeft: wide ? line : undefined,
              borderTop: wide ? undefined : line,
            }}
          >
            <Text size="sm" fw={600} mb="md">
              Chất ô nhiễm khác{' '}
              <Text span size="xs" c="dimmed" fw={400}>
                · trung bình theo ngày
              </Text>
            </Text>
            <SimpleGrid cols={{ base: 2, xs: 3, lg: 5 }} spacing="lg" verticalSpacing="md">
              {pollutants.map(([label, value]) => (
                <Metric key={label} label={label} value={fmtNum(value)} unit="µg/m³" size="sm" />
              ))}
            </SimpleGrid>
          </Box>
        </Box>
      </Paper>

      <Panel
        title="Đợt ô nhiễm"
        description="Một đợt là ít nhất 3 giờ liên tiếp có PM2.5 từ 115 µg/m³."
      >
        <SimpleGrid cols={{ base: 2, sm: 3, lg: figures.length }} spacing="lg" verticalSpacing="lg">
          {figures.map((figure) => (
            <Metric key={figure.label} {...figure} />
          ))}
        </SimpleGrid>
      </Panel>
    </Stack>
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
  const showRanking = !stationKey && compareRows.length > 1

  return (
    <Stack gap="lg">
      <PageHeader
        title="Tổng quan"
        description={
          meta
            ? `Mức PM2.5 và các chất ô nhiễm khác, từ ${fmtDate(meta.data_min)} đến ${fmtDate(meta.data_max)}.`
            : 'Mức trung bình và xu hướng theo ngày.'
        }
      />

      <FilterBar busy={loading && kpis != null}>
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
      </FilterBar>

      {error && <ErrorAlert title="Lỗi tải dữ liệu" message={error} />}

      {!kpis && loading && <LoadingBlock height={160} />}

      {kpis && (
        <Box
          aria-busy={loading || undefined}
          style={{ opacity: loading ? 0.55 : 1, transition: 'opacity 150ms ease-out' }}
        >
          <OverviewBody kpis={kpis} stationName={stationName} />
        </Box>
      )}

      {trends && (
        <Panel
          title="Xu hướng theo ngày"
          description={`${stationName ?? 'Trung bình 12 trạm'}. Vạch đứt là mốc 115 µg/m³ dùng để đếm đợt.`}
          busy={loading}
        >
          {trends.points.length === 0 ? (
            <EmptyState
              title="Không có điểm dữ liệu"
              description="Khoảng ngày đang chọn không có số đo. Thử chọn khoảng khác."
            />
          ) : (
            <TrendChart points={trends.points} height={320} />
          )}
        </Panel>
      )}

      {trends && trends.points.length > 0 && (
        <SimpleGrid cols={{ base: 1, lg: showRanking ? 2 : 1 }} spacing="md">
          {showRanking && (
            <Panel title="Xếp hạng trạm" description="PM2.5 trung bình trong khoảng đã chọn (µg/m³)." busy={loading}>
              <StationRanking rows={compareRows} />
            </Panel>
          )}
          <Panel
            title="Số ngày theo mức PM2.5"
            description={`Theo PM2.5 trung bình từng ngày${stationName ? ` tại ${stationName}` : ' của 12 trạm'}.`}
            busy={loading}
          >
            <LevelDays points={trends.points} />
          </Panel>
        </SimpleGrid>
      )}
    </Stack>
  )
}
