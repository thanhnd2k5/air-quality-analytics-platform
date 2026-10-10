import { Group, Select, TextInput } from '@mantine/core'
import type { Station } from '../api/stations'

type Props = {
  dateFrom: string
  dateTo: string
  stationKey: string | null
  stations: Station[]
  dataMin?: string
  dataMax?: string
  onDateFrom: (v: string) => void
  onDateTo: (v: string) => void
  onStationKey: (v: string | null) => void
  showStation?: boolean
}

export function DateStationFilters({
  dateFrom,
  dateTo,
  stationKey,
  stations,
  dataMin,
  dataMax,
  onDateFrom,
  onDateTo,
  onStationKey,
  showStation = true,
}: Props) {
  return (
    <Group align="flex-end" gap="sm" wrap="wrap">
      <TextInput
        label="Từ ngày"
        type="date"
        value={dateFrom}
        min={dataMin}
        max={dataMax}
        onChange={(e) => onDateFrom(e.currentTarget.value)}
      />
      <TextInput
        label="Đến ngày"
        type="date"
        value={dateTo}
        min={dataMin}
        max={dataMax}
        onChange={(e) => onDateTo(e.currentTarget.value)}
      />
      {showStation && (
        <Select
          label="Trạm"
          clearable
          searchable
          placeholder="Tất cả trạm"
          data={stations.map((s) => ({
            value: String(s.station_key),
            label: s.station_name,
          }))}
          value={stationKey}
          onChange={onStationKey}
          w={220}
        />
      )}
    </Group>
  )
}
