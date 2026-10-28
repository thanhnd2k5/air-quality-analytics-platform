import { Alert, Group, Loader, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useEffect, useState } from 'react'
import { fetchClusters, type ClusterGroup, type ClustersResponse, type KSelectionPoint } from '../api/clusters'

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

function accent(label: string) {
  return label === 'elevated_core' ? '#ea580c' : '#0d9488'
}

function silAt(grid: KSelectionPoint[], method: string, k: number) {
  return grid.find((point) => point.method === method && point.k === k)?.silhouette
}

function silText(value: number | undefined) {
  if (value == null) return '—'
  return value.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function selectionOption(grid: KSelectionPoint[]) {
  const ks = [2, 3, 4]
  const series = (method: string, name: string, color: string) => ({
    name,
    type: 'line' as const,
    data: ks.map((k) => silAt(grid, method, k) ?? null),
    symbol: 'circle',
    symbolSize: 10,
    color,
  })
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { top: 0 },
    grid: { left: 48, right: 16, top: 36, bottom: 28 },
    xAxis: { type: 'category' as const, name: 'K', data: ks.map(String) },
    yAxis: { type: 'value' as const, name: 'Silhouette', min: 0, max: 0.8 },
    series: [
      series('kmeans', 'KMeans', '#ea580c'),
      series('agglomerative_ward', 'Phân cấp Ward', '#2563eb'),
    ],
  }
}

function GroupCard({ group }: { group: ClusterGroup }) {
  return (
    <Paper withBorder p="md" radius="sm" style={{ borderTop: `3px solid ${accent(group.cluster_label)}` }}>
      <Text fw={600}>{group.label_vi}</Text>
      <Text size="sm" c="dimmed">
        {group.n_stations} trạm
      </Text>
      <Text fw={700} size="xl" mt="xs">
        {fmt(group.pm25_avg)}{' '}
        <Text span size="sm" fw={500} c="dimmed">
          µg/m³ PM2.5
        </Text>
      </Text>
      <Text size="sm" c="dimmed">
        NO₂ {fmt(group.no2_avg)} · CO {fmt(group.co_avg, 0)}
      </Text>
      <Text size="sm" mt="sm">
        {group.stations.map((station) => station.station_name).join(', ')}
      </Text>
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
    <Stack gap="md">
      <div>
        <Title order={2}>Phân cụm trạm</Title>
        <Text size="sm" c="dimmed">
          {data
            ? `Chọn số nhóm K trên hồ sơ 12 trạm, từ ${day(data.window_from)} đến ${day(data.window_to)}.`
            : 'Chọn số nhóm K trên hồ sơ 12 trạm.'}
        </Text>
      </div>

      {error && (
        <Alert color="red" title="Không tải được phân cụm">
          {error}
        </Alert>
      )}
      {!data && !error && (
        <Group>
          <Loader size="sm" />
          <Text size="sm">Đang tải…</Text>
        </Group>
      )}

      {data && (
        <>
          <Paper withBorder p="md" radius="sm">
            <Text fw={600} mb="xs">
              Silhouette theo K
            </Text>
            <ReactECharts option={selectionOption(data.k_grid)} style={{ height: 280 }} />
            <Text size="sm" mt="sm">
              Chọn K = 2 vì silhouette KMeans cao nhất ({silText(silAt(data.k_grid, 'kmeans', 2))}). K = 3 còn{' '}
              {silText(silAt(data.k_grid, 'kmeans', 3))}, K = 4 còn {silText(silAt(data.k_grid, 'kmeans', 4))}. Phân
              cấp Ward cũng cao nhất ở K = 2.
            </Text>
          </Paper>
          <Text size="sm" c="dimmed">
            K = 2 tách thành hai nhóm.
          </Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {data.groups.map((group) => (
              <GroupCard key={group.cluster_id} group={group} />
            ))}
          </SimpleGrid>
          {shunyiInCore && (
            <Text size="sm">
              Shunyi thuộc quận ngoại thành nhưng nằm ở nhóm lõi. Changping, Dingling và Huairou là nhóm ngoại ô phía bắc.
            </Text>
          )}
        </>
      )}
    </Stack>
  )
}
