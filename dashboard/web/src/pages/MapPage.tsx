import {
  Alert,
  Badge,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { fetchMapSnapshot, type MapSnapshotResponse } from '../api/map'

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

function clusterColor(label: string | null): string {
  if (label === 'elevated_core') return '#ea580c'
  if (label === 'cleaner_outskirts') return '#0d9488'
  return '#64748b'
}

function pmColor(pm: number | null): string {
  if (pm === null) return '#94a3b8'
  if (pm < 35) return '#22c55e'
  if (pm < 75) return '#eab308'
  if (pm < 115) return '#f97316'
  return '#dc2626'
}

export function MapPage() {
  const [colorMode, setColorMode] = useState<'cluster' | 'pm25'>('cluster')
  const [dateDay, setDateDay] = useState('')
  const [data, setData] = useState<MapSnapshotResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchMapSnapshot(dateDay || undefined)
      .then((res) => {
        if (!cancelled) {
          setData(res)
          if (!dateDay) setDateDay(res.date_day)
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
  }, [dateDay])

  const center = useMemo<[number, number]>(() => [39.95, 116.4], [])

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Bản đồ</Title>
        <Text size="sm" c="dimmed">
          12 trạm Bắc Kinh · Leaflet + OSM
        </Text>
      </div>

      <Group align="flex-end" wrap="wrap">
        <TextInput
          label="Ngày PM2.5"
          type="date"
          value={dateDay}
          min={data?.data_min}
          max={data?.data_max}
          onChange={(e) => setDateDay(e.currentTarget.value)}
        />
        <Group gap="xs">
          <Badge
            style={{ cursor: 'pointer' }}
            variant={colorMode === 'cluster' ? 'filled' : 'outline'}
            color="teal"
            onClick={() => setColorMode('cluster')}
          >
            Màu theo cluster
          </Badge>
          <Badge
            style={{ cursor: 'pointer' }}
            variant={colorMode === 'pm25' ? 'filled' : 'outline'}
            color="orange"
            onClick={() => setColorMode('pm25')}
          >
            Màu theo PM2.5
          </Badge>
        </Group>
      </Group>

      {data && (
        <Text size="xs" c="dimmed">
          {data.coordinate_note} · ngày hiển thị: {data.date_day}
        </Text>
      )}

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

      {data && !error && (
        <Paper withBorder radius="sm" style={{ overflow: 'hidden' }}>
          <MapContainer
            center={center}
            zoom={10}
            style={{ height: 520, width: '100%' }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitBounds points={data.points} />
            {data.points.map((p) => {
              const color =
                colorMode === 'cluster'
                  ? clusterColor(p.cluster_label)
                  : pmColor(p.pm25_ug_m3_avg)
              return (
                <CircleMarker
                  key={p.station_key}
                  center={[p.latitude, p.longitude]}
                  radius={10}
                  pathOptions={{
                    color: '#fff',
                    weight: 1,
                    fillColor: color,
                    fillOpacity: 0.9,
                  }}
                >
                  <Popup>
                    <strong>{p.station_name}</strong>
                    <br />
                    Quận: {p.district ?? '—'}
                    <br />
                    Cluster: {p.cluster_label ?? '—'}
                    <br />
                    PM2.5 ngày:{' '}
                    {p.pm25_ug_m3_avg != null
                      ? `${p.pm25_ug_m3_avg.toFixed(1)} µg/m³`
                      : '—'}
                    <br />
                    Coords: {p.coordinate_status ?? '—'}
                  </Popup>
                </CircleMarker>
              )
            })}
          </MapContainer>
        </Paper>
      )}
    </Stack>
  )
}
