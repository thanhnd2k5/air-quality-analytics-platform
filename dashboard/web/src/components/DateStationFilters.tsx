import { Select } from '@mantine/core'
import type { Station } from '../api/stations'
import { DateField } from './DateField'

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

/** Date range + station controls; rendered inline so a page can add its own filters beside them. */
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
    <>
      <DateField label="Từ ngày" value={dateFrom} min={dataMin} max={dateTo || dataMax} onChange={onDateFrom} />
      <DateField label="Đến ngày" value={dateTo} min={dateFrom || dataMin} max={dataMax} onChange={onDateTo} />
      {showStation && (
        <Select
          label="Trạm"
          clearable
          searchable
          placeholder="Tất cả 12 trạm"
          data={stations.map((s) => ({
            value: String(s.station_key),
            label: s.station_name,
          }))}
          value={stationKey}
          onChange={onStationKey}
          w={220}
        />
      )}
    </>
  )
}
