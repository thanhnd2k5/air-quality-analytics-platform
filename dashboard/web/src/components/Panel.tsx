import { Box, Group, Loader, Paper, Text, Title, type PaperProps } from '@mantine/core'
import type { ReactNode } from 'react'

type PanelProps = PaperProps & {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  /** Keeps the previous content visible but dimmed while new data loads. */
  busy?: boolean
  children: ReactNode
}

/** A white card section: optional heading row, then content. */
export function Panel({ title, description, actions, busy, children, ...paper }: PanelProps) {
  return (
    <Paper withBorder p="lg" {...paper}>
      {(title || actions) && (
        <Group justify="space-between" align="flex-start" gap="sm" mb="md" wrap="wrap">
          <Box style={{ minWidth: 0, flex: '1 1 260px' }}>
            {title && <Title order={2}>{title}</Title>}
            {description && (
              <Text size="sm" c="dimmed" mt={4}>
                {description}
              </Text>
            )}
          </Box>
          {actions}
        </Group>
      )}
      <Box
        aria-busy={busy || undefined}
        style={{ opacity: busy ? 0.55 : 1, transition: 'opacity 150ms ease-out' }}
      >
        {children}
      </Box>
    </Paper>
  )
}

/** One row of filters above the content it controls. */
export function FilterBar({ children, busy }: { children: ReactNode; busy?: boolean }) {
  return (
    <Paper withBorder px="lg" py="md">
      <Group align="flex-end" gap="md" wrap="wrap">
        {children}
        {busy && (
          <Group gap={8} ml="auto" pb={8} aria-live="polite">
            <Loader size={14} />
            <Text size="xs" c="dimmed">
              Đang cập nhật…
            </Text>
          </Group>
        )}
      </Group>
    </Paper>
  )
}
