import { Alert, Badge, Loader, Stack, Table, Text, Title } from '@mantine/core'
import { useEffect, useState } from 'react'
import { fetchStations, type Station } from '../api/stations'

export function StationsPage() {
  const [stations, setStations] = useState<Station[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchStations()
      .then((data) => {
        if (!cancelled) {
          setStations(data)
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
  }, [])

  return (
    <Stack gap="md">
      <Title order={2}>Trạm</Title>
      <Text size="sm" c="dimmed">
        12 trạm quan trắc + nhãn cluster (mart.mart_station_cluster).
      </Text>

      {loading && <Loader size="sm" />}
      {error && (
        <Alert color="red" title="Không tải được danh sách trạm">
          {error}
        </Alert>
      )}

      {!loading && !error && (
        <Table striped highlightOnHover withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Tên trạm</Table.Th>
              <Table.Th>Quận</Table.Th>
              <Table.Th>Cluster</Table.Th>
              <Table.Th>Lat</Table.Th>
              <Table.Th>Lon</Table.Th>
              <Table.Th>Coords</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {stations.map((s) => (
              <Table.Tr key={s.station_key}>
                <Table.Td>{s.station_name}</Table.Td>
                <Table.Td>{s.district ?? '—'}</Table.Td>
                <Table.Td>
                  {s.cluster_label ? (
                    <Badge variant="light" color="teal">
                      {s.cluster_label}
                    </Badge>
                  ) : (
                    '—'
                  )}
                </Table.Td>
                <Table.Td>{s.latitude ?? '—'}</Table.Td>
                <Table.Td>{s.longitude ?? '—'}</Table.Td>
                <Table.Td>{s.coordinate_status ?? '—'}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}
