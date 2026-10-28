import { Badge, Box, Group, Text } from '@mantine/core'
import { PM25_LEVELS, pm25Level } from '../theme'

export function Dot({ color, size = 8 }: { color: string; size?: number }) {
  return (
    <Box
      component="span"
      aria-hidden
      w={size}
      h={size}
      style={{ display: 'inline-block', flex: 'none', borderRadius: 99, background: color }}
    />
  )
}

/** PM2.5 band as a coloured dot + text label (colour never carries the meaning alone). */
export function Pm25Badge({ value }: { value: number | null | undefined }) {
  const level = pm25Level(value)
  return (
    <Badge color="gray" c="dark" leftSection={<Dot color={level.color} />}>
      {level.label}
    </Badge>
  )
}

export function Pm25Legend() {
  return (
    <Group gap="md" wrap="wrap">
      {PM25_LEVELS.map(({ range, level }) => (
        <Group key={level.key} gap={6} wrap="nowrap">
          <Dot color={level.color} size={10} />
          <Text size="xs">
            {level.label}{' '}
            <Text span size="xs" c="dimmed">
              {range}
            </Text>
          </Text>
        </Group>
      ))}
    </Group>
  )
}
