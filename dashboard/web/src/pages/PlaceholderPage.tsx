import { Alert, Text, Title, Stack } from '@mantine/core'

type Props = {
  title: string
  note?: string
}

export function PlaceholderPage({ title, note }: Props) {
  return (
    <Stack gap="md">
      <Title order={2}>{title}</Title>
      <Alert color="gray" title="Đang dựng (P11)">
        <Text size="sm">
          {note ??
            'Trang này sẽ đọc dữ liệu từ marts qua FastAPI ở các bước P11b–P11d.'}
        </Text>
      </Alert>
    </Stack>
  )
}
