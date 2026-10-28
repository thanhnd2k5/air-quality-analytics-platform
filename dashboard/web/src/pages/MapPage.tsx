import { Box, Group, Paper, SegmentedControl, Stack, Text } from '@mantine/core'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { fetchMapSnapshot, type MapSnapshotResponse } from '../api/map'
import { DateField } from '../components/DateField'
import { PageHeader } from '../components/PageHeader'
import { FilterBar } from '../components/Panel'
import { Dot, Pm25Legend } from '../components/Pm25Badge'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { fmtNum } from '../format'
import { CLUSTER, INK, clusterInfo, pm25Level } from '../theme'

// Fix default marker assets unused; we use CircleMarker only.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl

function FitBounds({ points }: { points: MapSnapshotResponse['points'] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 0) return
    const bounds = L.latLngBounds(
      points.map((p) => [p.latitude, p.longitude] as [number, number]),
    )
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [map, points])
  return null
}

// Leaflet only measures its container on window resize; re-measure when the card itself
// changes size (layout settling, navbar toggle) so tiles and fitBounds use the real width.
function TrackSize() {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return null
}

function fmtDay(iso: string) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`
}

export function MapPage() {
  const [colorMode, setColorMode] = useState<'cluster' | 'pm25'>('cluster')
  // undefined = API default (latest day); only set when user picks a date
  const [queryDay, setQueryDay] = useState<string | undefined>(undefined)
  const [displayDay, setDisplayDay] = useState('')
  const [data, setData] = useState<MapSnapshotResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchMapSnapshot(queryDay)
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setDisplayDay(res.date_day)
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
  }, [queryDay])

  const center = useMemo<[number, number]>(() => [39.95, 116.4], [])

  return (
    <Stack gap="lg">
      <PageHeader
        title="Bản đồ trạm"
        description="12 trạm quan trắc tại Bắc Kinh, tô màu theo nhóm phân cụm hoặc theo PM2.5 của một ngày."
      />

      <FilterBar busy={loading && data != null}>
        <DateField
          label="Ngày PM2.5"
          value={displayDay}
          min={data?.data_min}
          max={data?.data_max}
          onChange={(v) => {
            setDisplayDay(v)
            setQueryDay(v || undefined)
          }}
        />
        <Box>
          <Text size="sm" fw={500} mb={4}>
            Tô màu theo
          </Text>
          <SegmentedControl
            value={colorMode}
            onChange={(v) => setColorMode(v as 'cluster' | 'pm25')}
            data={[
              { value: 'cluster', label: 'Nhóm phân cụm' },
              { value: 'pm25', label: 'PM2.5 trong ngày' },
            ]}
          />
        </Box>
      </FilterBar>

      {error && <ErrorAlert title="Không tải được bản đồ" message={error} />}
      {!data && loading && !error && <LoadingBlock height={520} />}

      {data && !error && (
        <Paper withBorder style={{ overflow: 'hidden' }}>
          <MapContainer
            center={center}
            zoom={10}
            style={{ height: 540, width: '100%' }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <TrackSize />
            <FitBounds points={data.points} />
            {data.points.map((p) => {
              const group = clusterInfo(p.cluster_label)
              const level = pm25Level(p.pm25_ug_m3_avg)
              const color = colorMode === 'cluster' ? group.color : level.color
              return (
                <CircleMarker
                  key={p.station_key}
                  center={[p.latitude, p.longitude]}
                  radius={10}
                  pathOptions={{
                    color: INK.primary,
                    opacity: 0.45,
                    weight: 1.5,
                    fillColor: color,
                    fillOpacity: 0.95,
                  }}
                >
                  <Popup>
                    <Text fw={650} size="sm" mb={4}>
                      {p.station_name}
                    </Text>
                    <Text size="xs">Quận: {p.district ?? '—'}</Text>
                    <Text size="xs">Nhóm: {group.label}</Text>
                    <Text size="xs">
                      PM2.5 ngày:{' '}
                      {p.pm25_ug_m3_avg != null
                        ? `${fmtNum(p.pm25_ug_m3_avg)} µg/m³ (${level.label})`
                        : '—'}
                    </Text>
                  </Popup>
                </CircleMarker>
              )
            })}
          </MapContainer>
          <Group
            justify="space-between"
            gap="md"
            px="lg"
            py="sm"
            wrap="wrap"
            style={{ borderTop: '1px solid var(--mantine-color-gray-3)' }}
          >
            {colorMode === 'cluster' ? (
              <Group gap="md">
                {Object.values(CLUSTER).map((c) => (
                  <Group key={c.label} gap={6} wrap="nowrap">
                    <Dot color={c.color} size={10} />
                    <Text size="xs">{c.label}</Text>
                  </Group>
                ))}
              </Group>
            ) : (
              <Pm25Legend />
            )}
            <Text size="xs" c="dimmed">
              Ngày hiển thị: {fmtDay(data.date_day)} · nhấn vào một trạm để xem chi tiết
            </Text>
          </Group>
        </Paper>
      )}
    </Stack>
  )
}
