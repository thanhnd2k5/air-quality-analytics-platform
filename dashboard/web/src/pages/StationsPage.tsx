import {
  Alert,
  Badge,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useEffect, useState } from 'react'
import { fetchStationCompare, type StationCompareRow } from '../api/compare'
import { fetchOverviewMeta, type OverviewMeta } from '../api/overview'
import { fetchStations, type Station } from '../api/stations'
import { DateStationFilters } from '../components/DateStationFilters'

function fmt(n: number | null | undefined) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(1)
}

function groupName(label: string | null) {
  if (label === 'elevated_core') return 'Lõi ô nhiễm cao'
  if (label === 'cleaner_outskirts') return 'Ngoại ô phía bắc'
  return label
}

export function StationsPage() {
  const [meta, setMeta] = useState<OverviewMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [rows, setRows] = useState<StationCompareRow[]>([])
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
    fetchStationCompare({ date_from: dateFrom, date_to: dateTo })
      .then((res) => {
        if (!cancelled) {
          setRows(res.rows)
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
  }, [dateFrom, dateTo])

  return (
    <Stack gap="md">
      <div>
        <Title order={2}>Trạm</Title>
        <Text size="sm" c="dimmed">
          Xếp hạng PM2.5 và số đợt theo trạm.
        </Text>
      </div>

      <DateStationFilters
        dateFrom={dateFrom}
        dateTo={dateTo}
        stationKey={null}
        stations={stations}
        dataMin={meta?.data_min}
        dataMax={meta?.data_max}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        onStationKey={() => undefined}
        showStation={false}
      />

      {loading && (
        <Group>
          <Loader size="sm" />
          <Text size="sm">Đang tải…</Text>
        </Group>
      )}
      {error && (
        <Alert color="red" title="Không tải được bảng so sánh">
          {error}
        </Alert>
      )}

      {!loading && !error && (
        <Table striped highlightOnHover withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Hạng</Table.Th>
              <Table.Th>Trạm</Table.Th>
              <Table.Th>Quận</Table.Th>
              <Table.Th>Nhóm</Table.Th>
              <Table.Th>PM2.5 TB</Table.Th>
              <Table.Th>Số đợt</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((r) => (
              <Table.Tr key={r.station_key}>
                <Table.Td>{r.rank_pm25}</Table.Td>
                <Table.Td>{r.station_name}</Table.Td>
                <Table.Td>{r.district ?? '—'}</Table.Td>
                <Table.Td>
                  {groupName(r.cluster_label) ? (
                    <Badge
                      variant="light"
                      tt="none"
                      color={
                        r.cluster_label === 'elevated_core' ? 'orange' : 'teal'
                      }
                    >
                      {groupName(r.cluster_label)}
                    </Badge>
                  ) : (
                    '—'
                  )}
                </Table.Td>
                <Table.Td>{fmt(r.pm25_avg)}</Table.Td>
                <Table.Td>{r.episode_count}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}
