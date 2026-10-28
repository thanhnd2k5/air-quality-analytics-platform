import { Badge, Box, Group, Paper, Select, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core'
import { useEffect, useMemo, useState } from 'react'
import {
  fetchAlertMeta,
  fetchAlertSummary,
  fetchAlertTimeline,
  type AlertMeta,
  type AlertSummary,
  type AlertTimeline,
  type ConfusionMatrix,
} from '../api/alerts'
import { fetchStations, type Station } from '../api/stations'
import { Chart } from '../components/Chart'
import { DateField } from '../components/DateField'
import { Metric } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { FilterBar, Panel } from '../components/Panel'
import { Dot } from '../components/Pm25Badge'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { fmtPct, fmtSigned } from '../format'
import { INK, NEUTRAL_SERIES, SERIES, STATUS } from '../theme'

function pct(v: number | null | undefined, d = 1) {
  return v == null ? '—' : fmtPct(v * 100, d)
}

function num(v: number) {
  return v.toLocaleString('vi-VN')
}

// Per-hour outcome colours; TN stays a quiet grey so the errors (FP, FN) stand out.
const OUTCOME = {
  TP: { label: 'Cảnh báo đúng (TP)', color: STATUS.good },
  FP: { label: 'Báo nhầm (FP)', color: STATUS.warning },
  FN: { label: 'Bỏ sót (FN)', color: STATUS.critical },
  TN: { label: 'Đúng là sạch (TN)', color: '#d5dde7' },
} as const
type OutcomeCode = keyof typeof OUTCOME

function outcomeOf(code: string) {
  return code in OUTCOME ? OUTCOME[code as OutcomeCode] : null
}

function tint(color: string) {
  return `color-mix(in srgb, ${color} 12%, white)`
}

function ConfusionCard({ title, m, highlight }: { title: string; m: ConfusionMatrix; highlight?: boolean }) {
  const cell = (code: string, label: string, v: number, color?: string) => (
    <Table.Td style={{ background: color ? tint(color) : 'var(--mantine-color-gray-0)', textAlign: 'center' }}>
      <Text fw={650} size="lg" className="tabular">
        {num(v)}
      </Text>
      <Group gap={6} justify="center" wrap="nowrap">
        {color && <Dot color={color} />}
        <Text size="xs" c="dimmed">
          {code}
          {/* Phones show the code only, so the 2×2 table fits without sideways scrolling. */}
          <Text span inherit visibleFrom="sm">
            {' '}· {label}
          </Text>
        </Text>
      </Group>
    </Table.Td>
  )
  return (
    <Paper
      withBorder
      p={{ base: 'md', sm: 'lg' }}
      style={highlight ? { borderColor: 'var(--mantine-color-brand-5)', boxShadow: '0 0 0 1px var(--mantine-color-brand-5)' } : undefined}
    >
      <Group justify="space-between" mb="md" wrap="nowrap" align="flex-start">
        <Box>
          <Title order={2}>{title}</Title>
          <Text size="xs" c={highlight ? 'brand.7' : 'dimmed'} fw={highlight ? 600 : 400} mt={2}>
            {highlight ? 'Mô hình được chọn' : 'Mốc so sánh đơn giản'}
          </Text>
        </Box>
        <Badge color={highlight ? 'brand' : 'gray'} size="lg" className="tabular" style={{ flex: 'none' }}>
          F1 {pct(m.f1)}
        </Badge>
      </Group>
      <Table.ScrollContainer minWidth={300}>
        <Table withTableBorder withColumnBorders>
          <Table.Thead>
            {/* Positive class first (Han, Kamber & Pei layout): TP top-left, TN bottom-right. */}
            <Table.Tr>
              <Table.Th style={{ whiteSpace: 'normal' }}>Thực tế \ Dự đoán</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>Cảnh báo</Table.Th>
              <Table.Th style={{ textAlign: 'center' }}>
                Không
                <Text span inherit visibleFrom="sm">
                  {' '}cảnh báo
                </Text>
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            <Table.Tr>
              <Table.Th>Vượt ngưỡng</Table.Th>
              {cell('TP', 'cảnh báo đúng', m.tp, STATUS.good)}
              {cell('FN', 'bỏ sót', m.fn, STATUS.critical)}
            </Table.Tr>
            <Table.Tr>
              <Table.Th>Dưới ngưỡng</Table.Th>
              {cell('FP', 'báo nhầm', m.fp, STATUS.warning)}
              {cell('TN', 'đúng là sạch', m.tn)}
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      <SimpleGrid cols={3} mt="md" spacing="md">
        <Metric label="Precision (P)" value={pct(m.precision)} size="sm" />
        <Metric label="Recall (R)" value={pct(m.recall)} size="sm" />
        <Metric
          label="Bắt kịp lúc bắt đầu"
          value={pct(m.onsets ? m.onsets_detected / m.onsets : null, 0)}
          hint={`${num(m.onsets_detected)} / ${num(m.onsets)} lần`}
          size="sm"
        />
      </SimpleGrid>
    </Paper>
  )
}

export function AlertsPage() {
  const [summary, setSummary] = useState<AlertSummary | null>(null)
  const [meta, setMeta] = useState<AlertMeta | null>(null)
  const [stations, setStations] = useState<Station[]>([])
  const [stationKey, setStationKey] = useState<string>('4')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [timeline, setTimeline] = useState<AlertTimeline | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([fetchAlertSummary('test'), fetchAlertMeta(), fetchStations()])
      .then(([s, m, st]) => {
        setSummary(s)
        setMeta(m)
        setStations(st)
        setDateFrom(m.default_from)
        setDateTo(m.default_to)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!dateFrom || !dateTo) return
    let cancelled = false
    setLoading(true)
    fetchAlertTimeline({ station_key: Number(stationKey), date_from: dateFrom, date_to: dateTo })
      .then((t) => {
        if (!cancelled) {
          setTimeline(t)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [stationKey, dateFrom, dateTo])

  // Prediction vs truth on one plot: the PM2.5 line, with a light band on every hour the model
  // raised an alert; below it, a thin strip coloured by each hour's outcome (TP/FP/FN/TN).
  const chartOption = useMemo(() => {
    const s = timeline?.series ?? []
    const x = s.map((p) => `${p.target_time.slice(8, 10)}/${p.target_time.slice(5, 7)} ${p.target_time.slice(11, 13)}h`)
    const threshold = timeline?.alert_threshold ?? 115
    const cutoff = timeline?.probability_cutoff ?? 0.5
    const peak = Math.max(threshold, ...s.map((p) => p.actual_pm25 ?? 0))
    const yMax = Math.ceil((peak * 1.08) / 50) * 50
    const dot = (color: string) =>
      `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>`
    // The hour, PM2.5 with unit, probability in %, and that hour's outcome.
    const tooltipFor = (params: { dataIndex: number }[]) => {
      const p = s[params[0]?.dataIndex ?? -1]
      if (!p) return ''
      const t = p.target_time
      const proba = p.predicted_proba
      const outcome = outcomeOf(p.outcome)
      return [
        `<b>${t.slice(8, 10)}/${t.slice(5, 7)}/${t.slice(0, 4)} ${t.slice(11, 16)}</b>`,
        `PM2.5 thực tế: <b>${p.actual_pm25 == null ? '—' : `${Math.round(p.actual_pm25)} µg/m³`}</b>`,
        `Xác suất cảnh báo: <b>${proba == null ? '—' : fmtPct(proba * 100)}</b>` +
          (proba == null ? '' : proba >= cutoff ? ' (≥ ngưỡng cắt → báo)' : ' (< ngưỡng cắt → không báo)'),
        outcome ? `${dot(outcome.color)}${outcome.label}` : '',
      ]
        .filter(Boolean)
        .join('<br/>')
    }
    return {
      tooltip: { trigger: 'axis', formatter: tooltipFor },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      legend: {
        data: [
          'PM2.5 thực tế',
          // The band is drawn at 13% opacity; its legend swatch needs more ink to be visible.
          { name: 'Mô hình phát cảnh báo', icon: 'rect', itemStyle: { color: SERIES.blue, opacity: 0.35 } },
        ],
      },
      // Fixed left edge (no containLabel) so both panels share exactly the same x positions.
      grid: [
        { left: 56, right: 16, top: 48, bottom: 78 },
        { left: 56, right: 16, height: 16, bottom: 34 },
      ],
      xAxis: [
        { type: 'category', data: x, gridIndex: 0, axisLabel: { show: false } },
        { type: 'category', data: x, gridIndex: 1, axisLine: { show: false } },
      ],
      yAxis: [
        { type: 'value', name: 'PM2.5 (µg/m³)', gridIndex: 0, min: 0, max: yMax },
        { type: 'value', gridIndex: 1, min: 0, max: 1, show: false },
      ],
      graphic: [
        { type: 'text', left: 4, bottom: 35, style: { text: 'Kết quả', fill: INK.muted, fontSize: 11 } },
      ],
      series: [
        {
          name: 'Mô hình phát cảnh báo',
          type: 'bar',
          data: s.map((p) => (p.predicted_alert === 1 ? yMax : null)),
          barWidth: '100%',
          itemStyle: { color: SERIES.blue, opacity: 0.13 },
          emphasis: { disabled: true },
          silent: true,
          z: 1,
        },
        {
          name: 'PM2.5 thực tế',
          type: 'line',
          data: s.map((p) => p.actual_pm25),
          showSymbol: false,
          color: NEUTRAL_SERIES.strong,
          z: 3,
          markLine: {
            symbol: 'none',
            silent: true,
            label: { formatter: `Ngưỡng ${threshold} µg/m³`, position: 'insideEndTop', color: INK.secondary, fontSize: 11 },
            lineStyle: { color: INK.secondary, type: 'dashed', width: 1 },
            data: [{ yAxis: threshold }],
          },
        },
        {
          name: 'Kết quả',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          barWidth: '100%',
          emphasis: { disabled: true },
          silent: true,
          data: s.map((p) => ({ value: 1, itemStyle: { color: outcomeOf(p.outcome)?.color ?? INK.border } })),
        },
      ],
    }
  }, [timeline])

  const outcomeCounts = useMemo(() => {
    const counts: Record<OutcomeCode, number> = { TP: 0, FP: 0, FN: 0, TN: 0 }
    for (const p of timeline?.series ?? []) if (p.outcome in counts) counts[p.outcome as OutcomeCode] += 1
    return counts
  }, [timeline])

  const stationName = stations.find((s) => String(s.station_key) === stationKey)?.station_name ?? ''

  return (
    <Stack gap="lg">
      <PageHeader
        title="Cảnh báo vượt ngưỡng PM2.5"
        description={`Dự đoán giờ tới PM2.5 có từ ${summary?.alert_threshold ?? 115} µg/m³ trở lên hay không. Đánh giá trên tập kiểm tra 07–12/2016.`}
      />

      {error && <ErrorAlert title="Không tải được dữ liệu cảnh báo" message={error} />}

      {summary ? (
        <Stack gap="xs">
          <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
            <ConfusionCard
              title={`Persistence: báo giờ tới nếu giờ này ≥ ${summary.alert_threshold ?? 115}`}
              m={summary.persistence}
            />
            <ConfusionCard title="Mô hình HistGradientBoosting" m={summary.model} highlight />
          </SimpleGrid>
          <Text size="xs" c="dimmed" className="tabular">
            Công thức: P = TP / (TP + FP) · R = TP / (TP + FN) · F1 = 2·P·R / (P + R)
          </Text>
        </Stack>
      ) : (
        !error && <LoadingBlock height={220} />
      )}

      <FilterBar busy={loading && timeline != null}>
        <Select
          label="Trạm"
          data={stations.map((s) => ({ value: String(s.station_key), label: s.station_name }))}
          value={stationKey}
          onChange={(v) => v && setStationKey(v)}
          allowDeselect={false}
          searchable
          w={220}
        />
        <DateField
          label="Từ ngày"
          value={dateFrom}
          min={meta?.data_min}
          max={dateTo || meta?.data_max}
          onChange={setDateFrom}
        />
        <DateField
          label="Đến ngày"
          value={dateTo}
          min={dateFrom || meta?.data_min}
          max={meta?.data_max}
          onChange={setDateTo}
        />
      </FilterBar>

      {timeline ? (
        <Panel
          title={`Diễn biến theo giờ${stationName ? ` · ${stationName}` : ''}`}
          description={`Đường: PM2.5 đo được (µg/m³). Nền xanh: giờ mô hình phát cảnh báo (xác suất ≥ ${Math.round(
            (timeline.probability_cutoff ?? 0.5) * 100,
          )}%). Dải màu dưới cùng: kết quả từng giờ.`}
          busy={loading}
        >
          <Chart
            option={chartOption}
            height={380}
            label={`PM2.5 theo giờ tại ${stationName}, các giờ mô hình phát cảnh báo, và kết quả từng giờ: ${outcomeCounts.TP} cảnh báo đúng, ${outcomeCounts.FP} báo nhầm, ${outcomeCounts.FN} bỏ sót.`}
          />
          <Group gap="lg" mt="sm" wrap="wrap">
            {(Object.keys(OUTCOME) as OutcomeCode[]).map((code) => (
              <Group key={code} gap={6} wrap="nowrap">
                <Dot color={OUTCOME[code].color} size={10} />
                <Text size="xs">
                  {OUTCOME[code].label}:{' '}
                  <Text span size="xs" fw={650} className="tabular">
                    {num(outcomeCounts[code])} giờ
                  </Text>
                </Text>
              </Group>
            ))}
          </Group>
        </Panel>
      ) : (
        !error && <LoadingBlock height={400} />
      )}

      {summary && (
        <Panel
          title="Theo trạm"
          description="Tập kiểm tra. F1 cao hơn mỗi hàng được in đậm; Chênh F1 = F1 mô hình − F1 persistence (điểm %)."
        >
          <Table.ScrollContainer minWidth={720}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Trạm</Table.Th>
                  <Table.Th ta="right">Giờ vượt ngưỡng</Table.Th>
                  <Table.Th ta="right">F1 mô hình</Table.Th>
                  <Table.Th ta="right">F1 persistence</Table.Th>
                  <Table.Th ta="right">Chênh F1</Table.Th>
                  <Table.Th ta="right">Recall mô hình</Table.Th>
                  <Table.Th ta="right">Recall persistence</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {summary.stations.map((s) => {
                  const modelWins = (s.f1_model ?? 0) >= (s.f1_persistence ?? 0)
                  const gap = s.f1_model != null && s.f1_persistence != null ? (s.f1_model - s.f1_persistence) * 100 : null
                  return (
                    <Table.Tr key={s.station_key}>
                      <Table.Td>{s.station_name}</Table.Td>
                      <Table.Td ta="right">{num(s.positives)}</Table.Td>
                      <Table.Td ta="right" fw={modelWins ? 650 : 400}>
                        {pct(s.f1_model)}
                      </Table.Td>
                      <Table.Td ta="right" fw={modelWins ? 400 : 650}>
                        {pct(s.f1_persistence)}
                      </Table.Td>
                      <Table.Td ta="right" fw={600}>
                        {fmtSigned(gap)}
                      </Table.Td>
                      <Table.Td ta="right">{pct(s.recall_model)}</Table.Td>
                      <Table.Td ta="right">{pct(s.recall_persistence)}</Table.Td>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Panel>
      )}
    </Stack>
  )
}
