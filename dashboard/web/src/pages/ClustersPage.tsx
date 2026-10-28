import { Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { useEffect, useState } from 'react'
import { fetchClusters, type ClusterGroup, type ClustersResponse, type KSelectionPoint } from '../api/clusters'
import { Chart } from '../components/Chart'
import { Metric } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { Dot } from '../components/Pm25Badge'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { CLUSTER, INK, NEUTRAL_SERIES, SERIES, clusterInfo } from '../theme'

function fmt(n: number | null | undefined, digits = 1) {
  if (n == null) return '—'
  return n.toLocaleString('vi-VN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function day(iso: string) {
  const [year, month, d] = iso.split('-')
  return `${d}/${month}/${year}`
}

function silAt(grid: KSelectionPoint[], method: string, k: number) {
  return grid.find((point) => point.method === method && point.k === k)?.silhouette
}

function silText(value: number | undefined) {
  if (value == null) return '—'
  return value.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// KMeans is the chosen method (series slot 1); Ward is the comparison, kept neutral.
function selectionOption(grid: KSelectionPoint[]) {
  const ks = [2, 3, 4]
  const series = (method: string, name: string, color: string, dashed = false) => ({
    name,
    type: 'line' as const,
    data: ks.map((k) => silAt(grid, method, k) ?? null),
    symbol: 'circle',
    symbolSize: 9,
    color,
    lineStyle: { type: dashed ? ('dashed' as const) : ('solid' as const) },
    itemStyle: { borderColor: '#fff', borderWidth: 2 },
  })
  // KMeans points carry their value; the chosen K is called out directly on the chart.
  // KMeans sits above Ward (they meet at K = 2); its labels go below the line, Ward runs above it.
  const kmeans = {
    ...series('kmeans', 'KMeans', SERIES.blue),
    z: 3,
    data: ks.map((k) => {
      const v = silAt(grid, 'kmeans', k) ?? null
      return k === 2
        ? {
            value: v,
            symbolSize: 12,
            label: {
              show: true,
              position: 'top' as const,
              align: 'left' as const,
              offset: [-6, -2],
              formatter: `Chọn K = 2 · ${silText(v ?? undefined)}`,
              color: INK.primary,
              fontWeight: 600,
            },
          }
        : {
            value: v,
            label: { show: true, position: 'bottom' as const, formatter: silText(v ?? undefined), color: INK.secondary },
          }
    }),
  }
  return {
    tooltip: { trigger: 'axis' as const, valueFormatter: (v: number) => silText(v) },
    legend: {},
    grid: { left: 8, right: 24, top: 48, bottom: 8, containLabel: true },
    xAxis: { type: 'category' as const, name: 'K', data: ks.map(String), boundaryGap: false },
    yAxis: { type: 'value' as const, name: 'Silhouette', min: 0, max: 0.8 },
    series: [kmeans, { ...series('agglomerative_ward', 'Phân cấp Ward', NEUTRAL_SERIES.soft, true), z: 2 }],
  }
}

/** How much higher the core group is than the northern outskirts, per pollutant, in %. */
function GroupGap({ groups }: { groups: ClusterGroup[] }) {
  const core = groups.find((g) => g.cluster_label === 'elevated_core')
  const outer = groups.find((g) => g.cluster_label === 'cleaner_outskirts')
  if (!core || !outer) return null
  // Pollutants differ by orders of magnitude (CO ≈ 1 000 µg/m³), so compare them as % gaps.
  const rows = (
    [
      ['PM2.5', core.pm25_avg, outer.pm25_avg, 1],
      ['NO₂', core.no2_avg, outer.no2_avg, 1],
      ['CO', core.co_avg, outer.co_avg, 0],
    ] as const
  ).filter(([, a, b]) => a != null && b != null && b !== 0)
  const pct = rows.map(([, a, b]) => ((a! - b!) / b!) * 100)
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: { dataIndex: number }[]) => {
        const i = params[0]?.dataIndex ?? -1
        const row = rows[i]
        if (!row) return ''
        const [name, a, b, digits] = row
        return `<b>${name}</b><br/>Nhóm A: ${fmt(a, digits)} µg/m³ · Nhóm B: ${fmt(b, digits)} µg/m³<br/>Nhóm A cao hơn <b>${pct[i].toFixed(0)}%</b>`
      },
    },
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${v}%` } },
    yAxis: { type: 'category', inverse: true, data: rows.map(([name]) => name), axisLine: { show: false } },
    series: [
      {
        type: 'bar',
        barWidth: 18,
        data: pct.map((v) => Number(v.toFixed(1))),
        itemStyle: { color: CLUSTER.elevated_core.color, borderRadius: [0, 4, 4, 0] },
        label: {
          show: true,
          position: 'right',
          formatter: (p: { value: number }) => `+${Math.round(p.value)}%`,
          color: INK.primary,
          fontWeight: 600,
        },
      },
    ],
  }
  return (
    <Panel
      title="Nhóm A cao hơn nhóm B bao nhiêu?"
      description="Chênh lệch nồng độ trung bình giữa hai nhóm, tính theo % so với nhóm B."
    >
      <Chart option={option} height={170} label="Phần trăm nhóm A cao hơn nhóm B với PM2.5, NO₂ và CO." />
    </Panel>
  )
}

function GroupCard({ group }: { group: ClusterGroup }) {
  const info = clusterInfo(group.cluster_label)
  return (
    <Paper withBorder p="lg" style={{ boxShadow: `inset 0 3px 0 ${info.color}` }}>
      <Group gap={8} wrap="nowrap">
        <Dot color={info.color} size={10} />
        <Title order={2}>{group.label_vi}</Title>
      </Group>
      <Text size="sm" c="dimmed" mt={2}>
        {group.n_stations} trạm
      </Text>
      <SimpleGrid cols={3} spacing="md" mt="md">
        <Metric label="PM2.5" value={fmt(group.pm25_avg)} unit="µg/m³" />
        <Metric label="NO₂" value={fmt(group.no2_avg)} unit="µg/m³" size="sm" />
        <Metric label="CO" value={fmt(group.co_avg, 0)} unit="µg/m³" size="sm" />
      </SimpleGrid>
      <Text size="xs" c="dimmed" fw={500} mt="md" mb={4}>
        Các trạm
      </Text>
      <Text size="sm">{group.stations.map((station) => station.station_name).join(', ')}</Text>
    </Paper>
  )
}

export function ClustersPage() {
  const [data, setData] = useState<ClustersResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchClusters()
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  const shunyiInCore = data?.groups.some(
    (group) =>
      group.cluster_label === 'elevated_core' &&
      group.stations.some((station) => station.station_name === 'Shunyi'),
  )

  return (
    <Stack gap="lg">
      <PageHeader
        title="Phân cụm trạm"
        description={
          data
            ? `Chọn số nhóm K trên hồ sơ 12 trạm, từ ${day(data.window_from)} đến ${day(data.window_to)}.`
            : 'Chọn số nhóm K trên hồ sơ 12 trạm.'
        }
      />

      {error && <ErrorAlert title="Không tải được phân cụm" message={error} />}
      {!data && !error && <LoadingBlock height={280} />}

      {data && (
        <>
          <Panel
            title="Chọn K theo silhouette"
            description={`Chọn K = 2 vì silhouette KMeans cao nhất (${silText(silAt(data.k_grid, 'kmeans', 2))}). K = 3 còn ${silText(silAt(data.k_grid, 'kmeans', 3))}, K = 4 còn ${silText(silAt(data.k_grid, 'kmeans', 4))}. Phân cấp Ward cũng cao nhất ở K = 2.`}
          >
            <Chart
              option={selectionOption(data.k_grid)}
              height={280}
              label="Silhouette của KMeans và phân cấp Ward theo K = 2, 3, 4; cao nhất ở K = 2."
            />
          </Panel>

          <Stack gap="sm">
            <Title order={2}>Hai nhóm trạm (K = 2)</Title>
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
              {data.groups.map((group) => (
                <GroupCard key={group.cluster_id} group={group} />
              ))}
            </SimpleGrid>
            {shunyiInCore && (
              <Text size="sm" c="dimmed">
                Nhóm B gồm ba trạm sát dãy núi phía bắc: Changping, Dingling và Huairou. Shunyi tuy thuộc quận
                ngoại thành nhưng có hồ sơ ô nhiễm giống nhóm A.
              </Text>
            )}
          </Stack>

          <GroupGap groups={data.groups} />
        </>
      )}
    </Stack>
  )
}
