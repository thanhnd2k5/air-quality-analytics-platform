import { DatePickerInput } from '@mantine/dates'
import { IconCalendar } from '@tabler/icons-react'

type Props = {
  label: string
  /** ISO day, 'YYYY-MM-DD' ('' while unknown). */
  value: string
  onChange: (value: string) => void
  min?: string
  max?: string
}

/** Calendar picker shown as DD/MM/YYYY; reads and writes ISO day strings. */
export function DateField({ label, value, onChange, min, max }: Props) {
  return (
    <DatePickerInput
      label={label}
      value={value || null}
      onChange={(v) => v && onChange(v)}
      minDate={min}
      maxDate={max}
      valueFormat="DD/MM/YYYY"
      leftSection={<IconCalendar size={16} stroke={1.5} />}
      leftSectionPointerEvents="none"
      popoverProps={{ shadow: 'md' }}
      w={168}
    />
  )
}
