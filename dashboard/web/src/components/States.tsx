import { Alert, Button, Paper, Skeleton, Stack, Text } from '@mantine/core'
import { IconAlertCircle, IconDatabaseOff } from '@tabler/icons-react'

/** Placeholder with the same footprint as the content it stands in for (no layout jump). */
export function LoadingBlock({ height = 320 }: { height?: number }) {
  return (
    <Paper withBorder p="lg" aria-busy="true" aria-label="Đang tải">
      <Skeleton h={14} w={180} mb="md" />
      <Skeleton h={height} />
    </Paper>
  )
}

export function ErrorAlert({ title, message }: { title: string; message: string }) {
  return (
    <Alert color="red" title={title} icon={<IconAlertCircle size={18} />}>
      <Stack gap="xs" align="flex-start">
        <Text size="sm" style={{ overflowWrap: 'anywhere' }}>
          {message}
        </Text>
        <Button size="xs" variant="white" color="red" onClick={() => window.location.reload()}>
          Tải lại trang
        </Button>
      </Stack>
    </Alert>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <Stack align="center" gap={6} py="xl">
      <IconDatabaseOff size={28} stroke={1.5} color="var(--mantine-color-gray-5)" aria-hidden />
      <Text fw={600} size="sm">
        {title}
      </Text>
      {description && (
        <Text size="sm" c="dimmed" ta="center" maw={420}>
          {description}
        </Text>
      )}
    </Stack>
  )
}
