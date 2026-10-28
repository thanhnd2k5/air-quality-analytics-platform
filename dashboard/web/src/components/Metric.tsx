import { Group, Paper, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'

type MetricProps = {
  label: ReactNode
  value: ReactNode
  unit?: ReactNode
  hint?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  children?: ReactNode
}

const VALUE_SIZE = { sm: 20, md: 26, lg: 44 }

/** Label above a number (+ unit). Values stay in ink colour; status goes in a labelled badge. */
export function Metric({ label, value, unit, hint, size = 'md', children }: MetricProps) {
  return (
    <Stack gap={6}>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Group gap={6} align="baseline" wrap="nowrap">
        <Text fz={VALUE_SIZE[size]} fw={650} lh={1.1} className="tabular">
          {value}
        </Text>
        {unit && (
          <Text size="sm" c="dimmed">
            {unit}
          </Text>
        )}
      </Group>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
      {children}
    </Stack>
  )
}

/** A Metric on its own card (KPI tile). */
export function StatCard(props: MetricProps) {
  return (
    <Paper withBorder p="lg">
      <Metric {...props} />
    </Paper>
  )
}
