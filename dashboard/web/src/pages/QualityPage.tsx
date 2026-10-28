import { Box, Button, Group, Paper, Progress, SimpleGrid, Stack, Text, Tooltip } from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import { useEffect, useState, type ReactNode } from 'react'
import {
  fetchQualitySummary,
  fetchServices,
  type PipelineRun,
  type QualitySummary,
  type ServiceCheck,
} from '../api/quality'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { Dot } from '../components/Pm25Badge'
import { fmtNum, fmtPct } from '../format'
import { INK, STATUS } from '../theme'

const REFRESH_SECONDS = 30
const HISTORY = 30 // probes kept per service for the strip (this browser session only)
const API = 'API dashboard'

type Tone = 'good' | 'critical' | 'neutral'
const TONE: Record<Tone, string> = { good: STATUS.good, critical: STATUS.critical, neutral: INK.muted }

// Data-quality flag set when the hour is cleaned (see docs/DATA_PREPROCESSING.md).
const FLAG: Record<string, { label: string; color: string }> = {
  OK: { label: 'Đủ số đo', color: STATUS.good },
  MISSING_MEASUREMENT: { label: 'Thiếu số đo', color: STATUS.warning },
  SUSPECT_CAP: { label: 'Chạm trần thiết bị', color: STATUS.critical },
}

type Sample = { ok: boolean; ms: number; at: string }

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function fmtClock(d: Date) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** ISO timestamp → "28/10/2026 17:19" in the viewer's time zone. */
function fmtWhen(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fmtDay(iso: string | null | undefined) {
  return iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '—'
}

function failedStep(run: PipelineRun) {
  return run.steps.find((s) => s.status !== 'ok' && s.status !== 'skipped')
}

type Check = { name: string; detail: string; value: string; tone: Tone; extra?: ReactNode }

/** Status-page row: dot, what is checked, the reading on the right. */
function CheckList({ checks }: { checks: Check[] }) {
  return (
    <Stack gap={0}>
      {checks.map((c, i) => (
        <Group
          key={c.name}
          justify="space-between"
          wrap="nowrap"
          gap="md"
          py={12}
          style={i ? { borderTop: `1px solid ${INK.border}` } : undefined}
        >
          <Group gap={12} wrap="nowrap" style={{ minWidth: 0 }}>
            <Dot color={TONE[c.tone]} size={10} />
            <Box style={{ minWidth: 0 }}>
              <Text size="sm" fw={600}>
                {c.name}
              </Text>
              <Text size="xs" c="dimmed" lineClamp={1} title={c.detail}>
                {c.detail}
              </Text>
            </Box>
          </Group>
          <Group gap="md" wrap="nowrap">
            {c.extra}
            <Text size="sm" fw={600} className="tabular" ta="right" miw={84} style={{ whiteSpace: 'nowrap' }}>
              {c.value}
            </Text>
          </Group>
        </Group>
      ))}
    </Stack>
  )
}

/** Last probes, oldest left; empty slots until the session has collected enough. */
function HistoryStrip({ samples }: { samples: Sample[] }) {
  const slots: (Sample | null)[] = [...Array(Math.max(0, HISTORY - samples.length)).fill(null), ...samples]
  return (
    <Group gap={2} wrap="nowrap" visibleFrom="sm" aria-label={`${samples.length} lần kiểm tra gần nhất`}>
      {slots.map((s, i) =>
        s ? (
          <Tooltip key={i} label={`${fmtClock(new Date(s.at))} · ${s.ok ? `${fmtNum(s.ms, 0)} ms` : 'lỗi'}`}>
            <Box w={4} h={18} style={{ borderRadius: 2, background: s.ok ? STATUS.good : STATUS.critical }} />
          </Tooltip>
        ) : (
          <Box key={i} w={4} h={18} style={{ borderRadius: 2, background: INK.grid }} />
        ),
      )}
    </Group>
  )
}

function dataChecks(q: QualitySummary | null, dbDown: boolean, apiDown: boolean): Check[] {
  if (!q || dbDown) {
    const unknown = {
      detail: apiDown ? 'Cần kết nối API' : 'Cần kết nối cơ sở dữ liệu',
      value: 'Không rõ',
      tone: 'neutral' as const,
    }
    return ['Đối soát nạp dữ liệu', 'Khoá (trạm, giờ)', 'dbt test', 'Pipeline gần nhất'].map((name) => ({
      name,
      ...unknown,
    }))
  }
  const rec = q.reconcile
  const aq = rec?.datasets[0]
  const dupes = q.warehouse.fact_rows - q.warehouse.distinct_keys
  const dbt = q.dbt_tests
  const run = q.last_run
  return [
    {
      name: 'Đối soát nạp dữ liệu',
      detail: aq
        ? `${fmtNum(aq.target_rows, 0)} / ${fmtNum(aq.source_rows, 0)} dòng nguồn → staging`
        : 'Chưa chạy bước staging',
      value: !rec ? 'Chưa có' : rec.ok ? 'Khớp' : 'Lệch',
      tone: !rec ? 'neutral' : rec.ok ? 'good' : 'critical',
    },
    {
      name: 'Khoá (trạm, giờ)',
      detail: 'Mỗi trạm chỉ có một dòng cho mỗi giờ trong bảng sự kiện',
      value: dupes ? `${fmtNum(dupes, 0)} trùng` : 'Không trùng',
      tone: dupes ? 'critical' : 'good',
    },
    {
      name: 'dbt test',
      detail: dbt ? `Chạy lúc ${fmtWhen(dbt.finished_at)}` : 'Chưa có kết quả',
      value: dbt ? `${dbt.passed}/${dbt.total} đạt` : 'Chưa có',
      tone: !dbt ? 'neutral' : dbt.errors === 0 && dbt.passed === dbt.total ? 'good' : 'critical',
    },
    {
      name: 'Pipeline gần nhất',
      detail: run
        ? `${fmtWhen(run.finished_at)} · ${run.scope}${run.total_seconds ? ` · ${fmtNum(run.total_seconds / 60, 1)} phút` : ''}`
        : 'Chưa chạy run_all.py',
      value: !run ? 'Chưa có' : run.ok ? 'Thành công' : `Lỗi: ${failedStep(run)?.step ?? '?'}`,
      tone: !run ? 'neutral' : run.ok ? 'good' : 'critical',
    },
  ]
}

function WarehousePanel({ q }: { q: QualitySummary }) {
  const w = q.warehouse
  const rows = w.fact_rows || 1
  const flagsTotal = q.status_counts.reduce((s, c) => s + c.rows, 0) || 1
  const lastLoad = q.loads.reduce<string | null>(
    (latest, l) => (l.last_loaded_at && (!latest || l.last_loaded_at > latest) ? l.last_loaded_at : latest),
    null,
  )
  const pollutants = q.columns.filter((c) => c.kind === 'Chất ô nhiễm')
  const weather = q.columns.filter((c) => c.kind === 'Thời tiết')
  const maxPollutant = Math.max(...pollutants.map((c) => (c.missing_at_source / rows) * 100))
  const weatherMissing = weather.reduce((s, c) => s + c.missing_at_source, 0)
  const weatherFilled = weather.reduce((s, c) => s + c.filled, 0)
  const metrics = [
    { label: 'Giờ-trạm trong kho', value: fmtNum(w.fact_rows, 0) },
    { label: 'Trạm', value: fmtNum(w.stations, 0) },
    { label: 'Khoảng thời gian', value: `${fmtDay(w.first_hour)} – ${fmtDay(w.last_hour)}` },
    { label: 'Nạp lần cuối', value: fmtWhen(lastLoad) },
  ]
  return (
    <Panel title="Dữ liệu trong kho">
      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="lg">
        {metrics.map((m) => (
          <Stack key={m.label} gap={4}>
            <Text size="xs" c="dimmed" fw={500}>
              {m.label}
            </Text>
            <Text fw={650} fz={{ base: 15, sm: 18 }} className="tabular">
              {m.value}
            </Text>
          </Stack>
        ))}
      </SimpleGrid>
      <Text size="xs" c="dimmed" fw={500} mt="xl" mb={8}>
        Cờ chất lượng từng giờ
      </Text>
      <Progress.Root size={12} radius="sm">
        {q.status_counts.map((c) => (
          <Progress.Section
            key={c.status}
            value={(c.rows / flagsTotal) * 100}
            color={FLAG[c.status]?.color ?? INK.muted}
          />
        ))}
      </Progress.Root>
      <Group gap="lg" mt={10} wrap="wrap">
        {q.status_counts.map((c) => (
          <Group key={c.status} gap={6} wrap="nowrap">
            <Dot color={FLAG[c.status]?.color ?? INK.muted} size={8} />
            <Text size="sm">{FLAG[c.status]?.label ?? c.status}</Text>
            <Text size="sm" c="dimmed" className="tabular">
              {c.rows / flagsTotal < 0.001 ? `${fmtNum(c.rows, 0)} giờ` : fmtPct((c.rows / flagsTotal) * 100)}
            </Text>
          </Group>
        ))}
      </Group>
      <Text size="xs" c="dimmed" mt="md">
        Chất ô nhiễm thiếu tối đa {fmtPct(maxPollutant)} số giờ, giữ NULL · thời tiết đã lấp{' '}
        {fmtPct(weatherMissing ? (weatherFilled / weatherMissing) * 100 : 100, 0)} từ Open-Meteo.
      </Text>
    </Panel>
  )
}

export function QualityPage() {
  const [services, setServices] = useState<ServiceCheck[] | null>(null)
  const [history, setHistory] = useState<Record<string, Sample[]>>({})
  const [apiDown, setApiDown] = useState(false)
  const [apiMs, setApiMs] = useState<number | null>(null)
  const [q, setQ] = useState<QualitySummary | null>(null)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)
  const [busy, setBusy] = useState(true)
  const [round, setRound] = useState(0)

  // Poll: services live every time; the summary is cached by the API per data version, so
  // re-reading it is cheap and picks up a pipeline run within one interval.
  useEffect(() => {
    let cancelled = false
    const tick = (fresh: boolean) => {
      const started = performance.now()
      const probe = fetchServices()
        .then((res) => {
          if (cancelled) return
          // The API row is timed here, in the browser: the round trip a page view pays.
          const ms = performance.now() - started
          setApiDown(false)
          setApiMs(ms)
          setServices(res.services)
          setHistory((h) => {
            const next: Record<string, Sample[]> = {
              ...h,
              [API]: [...(h[API] ?? []), { ok: true, ms, at: res.checked_at }].slice(-HISTORY),
            }
            for (const s of res.services) {
              next[s.name] = [...(h[s.name] ?? []), { ok: s.ok, ms: s.latency_ms, at: res.checked_at }].slice(-HISTORY)
            }
            return next
          })
        })
        .catch(() => {
          if (cancelled) return
          setApiDown(true)
          setHistory((h) => ({
            ...h,
            [API]: [...(h[API] ?? []), { ok: false, ms: 0, at: new Date().toISOString() }].slice(-HISTORY),
          }))
        })
      const summary = fetchQualitySummary(fresh)
        .then((s) => !cancelled && setQ(s))
        .catch(() => undefined) // shown as "Không rõ" through the service checks
      Promise.allSettled([probe, summary]).then(() => {
        if (cancelled) return
        setCheckedAt(new Date())
        setBusy(false)
      })
    }
    tick(round > 0)
    const id = window.setInterval(() => tick(true), REFRESH_SECONDS * 1000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [round])

  const dbDown = apiDown || services?.find((s) => s.name === 'PostgreSQL')?.ok === false
  const apiCheck: Check = {
    name: API,
    detail: apiDown ? 'Không gọi được API (cổng 8100)' : 'FastAPI · cổng 8100',
    value: apiDown ? 'Mất kết nối' : apiMs == null ? '—' : `${fmtNum(apiMs, 0)} ms`,
    tone: apiDown ? 'critical' : apiMs == null ? 'neutral' : 'good',
    extra: <HistoryStrip samples={history[API] ?? []} />,
  }
  // With the API down nothing behind it can be probed, so its row stands alone.
  const serviceChecks: Check[] = apiDown
    ? [apiCheck]
    : [
        apiCheck,
        ...(services ?? []).map((s): Check => ({
          name: s.name,
          detail: s.ok ? s.role : (s.detail ?? s.role),
          value: s.ok ? `${fmtNum(s.latency_ms, 0)} ms` : 'Mất kết nối',
          tone: s.ok ? 'good' : 'critical',
          extra: <HistoryStrip samples={history[s.name] ?? []} />,
        })),
      ]
  const data = dataChecks(q, dbDown, apiDown)
  const failing = [...serviceChecks, ...data].filter((c) => c.tone === 'critical')
  const overallTone: Tone = !checkedAt ? 'neutral' : failing.length ? 'critical' : 'good'

  return (
    <Stack gap="lg">
      <PageHeader
        title="Chất lượng dữ liệu"
        description="Theo dõi kho dữ liệu, data lake và lần nạp gần nhất."
        actions={
          <Button
            variant="default"
            leftSection={<IconRefresh size={16} />}
            onClick={() => {
              setBusy(true)
              setRound((r) => r + 1)
            }}
            loading={busy}
          >
            Kiểm tra lại
          </Button>
        }
      />

      <Paper withBorder px="lg" py="md">
        <Group justify="space-between" wrap="wrap" gap="sm">
          <Group gap={12} wrap="nowrap">
            <Box
              component="span"
              className={overallTone === 'good' ? 'live-dot' : undefined}
              w={12}
              h={12}
              style={{ borderRadius: 99, background: TONE[overallTone], color: TONE[overallTone], flex: 'none' }}
            />
            <Text fw={650} fz={18}>
              {overallTone === 'neutral'
                ? 'Đang kiểm tra…'
                : failing.length
                  ? `${failing.length} kiểm tra lỗi: ${failing.map((c) => c.name).join(', ')}`
                  : 'Mọi kiểm tra đều đạt'}
            </Text>
          </Group>
          <Text size="sm" c="dimmed" className="tabular">
            {checkedAt ? `Cập nhật ${fmtClock(checkedAt)} · tự làm mới mỗi ${REFRESH_SECONDS} giây` : ''}
          </Text>
        </Group>
      </Paper>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <Panel title="Dịch vụ" description="Đo phản hồi mỗi lần kiểm tra; vạch là các lần gần nhất trong phiên này.">
          <CheckList checks={serviceChecks} />
        </Panel>
        <Panel title="Kiểm tra dữ liệu" description="Từ kho và lần chạy scripts/run_all.py gần nhất.">
          <CheckList checks={data} />
        </Panel>
      </SimpleGrid>

      {q && !dbDown && <WarehousePanel q={q} />}
    </Stack>
  )
}
