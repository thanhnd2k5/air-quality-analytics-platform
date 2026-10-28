import { Box, Group, Modal, Stack, Text } from '@mantine/core'
import type { AlertPoint } from '../api/alerts'
import { fmtNum, fmtPct } from '../format'
import { INK, SERIES } from '../theme'

const OUTCOME_VI: Record<string, string> = {
  TP: 'cảnh báo đúng',
  FP: 'báo nhầm',
  FN: 'bỏ sót',
  TN: 'đúng là sạch',
}

function steps(cutoff: string): [string, string][] {
  return [
    [
      'Đầu vào',
      'Tại giờ t, lấy những số đã biết: PM2.5 giờ này và các giờ trước, PM10, CO, NO₂, thời tiết, giờ trong ngày, mùa, trạm.',
    ],
    ['Nhiều cây quyết định nhỏ', 'Cây đầu tiên đoán thô; mỗi cây sau học sửa phần mà các cây trước còn đoán sai.'],
    [
      'Cộng điểm → xác suất',
      'Điểm của tất cả các cây cộng lại, qua hàm sigmoid thành xác suất 0–100% rằng giờ tới PM2.5 ≥ 115 µg/m³.',
    ],
    ['So với ngưỡng', `Xác suất ≥ ${cutoff} thì phát cảnh báo. Ngưỡng này được chọn trên tập validation (01–06/2016).`],
  ]
}

/** The hour that shows the model best: an onset it caught (persistence could not), else any hit. */
function pickExample(series: AlertPoint[]) {
  const scored = series.filter((p) => p.predicted_proba != null)
  const top = (points: AlertPoint[]) =>
    points.reduce<AlertPoint | undefined>(
      (best, p) => (!best || (p.predicted_proba ?? 0) > (best.predicted_proba ?? 0) ? p : best),
      undefined,
    )
  return (
    top(scored.filter((p) => p.outcome === 'TP' && !p.persistence_alert)) ??
    top(scored.filter((p) => p.outcome === 'TP')) ??
    scored[0]
  )
}

function fmtHour(iso: string) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)} ${iso.slice(11, 16)}`
}

/** 0–100% track, the model's probability filled in, the cut-off marked. */
function ProbabilityBar({ proba, cutoff }: { proba: number; cutoff: number }) {
  return (
    <Box>
      <Box pos="relative" h={10} style={{ borderRadius: 99, background: INK.grid }}>
        <Box h={10} w={`${proba * 100}%`} style={{ borderRadius: 99, background: SERIES.blue }} />
        <Box
          pos="absolute"
          top={-4}
          left={`${cutoff * 100}%`}
          w={2}
          h={18}
          style={{ background: INK.primary, transform: 'translateX(-1px)' }}
        />
      </Box>
      <Box pos="relative" h={16} mt={4}>
        <Text size="xs" c="dimmed" pos="absolute" left={0}>
          0%
        </Text>
        <Text size="xs" fw={600} pos="absolute" left={`${cutoff * 100}%`} style={{ transform: 'translateX(-50%)' }}>
          ngưỡng {fmtPct(cutoff * 100, 0)}
        </Text>
        <Text size="xs" c="dimmed" pos="absolute" right={0}>
          100%
        </Text>
      </Box>
    </Box>
  )
}

type Props = {
  opened: boolean
  onClose: () => void
  /** Hours of the timeline on screen; the example is taken from them. */
  series: AlertPoint[]
  station: string
  cutoff: number
}

export function ModelExplainer({ opened, onClose, series, station, cutoff }: Props) {
  const example = pickExample(series)
  const cutoffText = fmtPct(cutoff * 100, 0)
  return (
    <Modal opened={opened} onClose={onClose} centered size="lg" title={<Text fw={650}>Mô hình quyết định thế nào?</Text>}>
      <Stack gap="md">
        {steps(cutoffText).map(([title, text], i) => (
          <Group key={title} gap="sm" wrap="nowrap" align="flex-start">
            <Box
              w={24}
              h={24}
              style={{
                flex: 'none',
                borderRadius: 99,
                display: 'grid',
                placeItems: 'center',
                background: 'var(--mantine-color-brand-0)',
                color: 'var(--mantine-color-brand-7)',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {i + 1}
            </Box>
            <Box>
              <Text size="sm" fw={600}>
                {title}
              </Text>
              <Text size="sm" c="dimmed">
                {text}
              </Text>
            </Box>
          </Group>
        ))}

        {example && example.predicted_proba != null && (
          <Box mt="xs" p="md" style={{ borderRadius: 8, background: 'var(--mantine-color-gray-0)' }}>
            <Text size="sm" fw={600} mb={10}>
              Ví dụ thật · {station}, {fmtHour(example.target_time)}
            </Text>
            <Stack gap={10}>
              <Text size="sm">
                {example.persistence_alert
                  ? 'Giờ trước PM2.5 đã từ 115 µg/m³ trở lên, nên cách đơn giản (persistence) cũng báo.'
                  : 'Giờ trước PM2.5 còn dưới 115 µg/m³, nên cách đơn giản (persistence) không báo.'}
              </Text>
              <ProbabilityBar proba={example.predicted_proba} cutoff={cutoff} />
              <Text size="sm">
                Mô hình tính ra <b>{fmtPct(example.predicted_proba * 100)}</b>{' '}
                {example.predicted_proba >= cutoff ? '≥' : '<'} ngưỡng {cutoffText} →{' '}
                <b>{example.predicted_alert ? 'phát cảnh báo' : 'không cảnh báo'}</b>.
              </Text>
              <Text size="sm">
                Thực tế: PM2.5 = {fmtNum(example.actual_pm25)} µg/m³ →{' '}
                <b>{OUTCOME_VI[example.outcome] ?? example.outcome}</b>.
              </Text>
            </Stack>
          </Box>
        )}
      </Stack>
    </Modal>
  )
}
