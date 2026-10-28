import { Group, Stack, Text, Title } from '@mantine/core'
import { useEffect, type ReactNode } from 'react'

type Props = {
  title: string
  description?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: Props) {
  useEffect(() => {
    document.title = `${title} · Chất lượng không khí Bắc Kinh`
  }, [title])

  return (
    <Group justify="space-between" align="flex-end" gap="md" wrap="wrap">
      <Stack gap={4} maw={760}>
        <Title order={1}>{title}</Title>
        {description && (
          <Text size="sm" c="dimmed">
            {description}
          </Text>
        )}
      </Stack>
      {actions}
    </Group>
  )
}
