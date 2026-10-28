import { Alert, Button, Group, Paper, Progress, SimpleGrid, Stack, Text } from '@mantine/core'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'
import { useEffect, useState, type ReactNode } from 'react'
import { fetchDbHealth, fetchQualitySummary, type PipelineRun, type QualitySummary } from '../api/quality'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { Dot } from '../components/Pm25Badge'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { fmtNum, fmtPct } from '../format'
import { INK, STATUS } from '../theme'

type Tone = 'good' | 'critical' | 'neutral'
const TONE: Record<Tone, string> = { good: STATUS.good, critical: STATUS.critical, neutral: INK.muted }

// Data-quality flag set when the hour is cleaned (see docs/DATA_PREPROCESSING.md).
const FLAG: Record<string, { label: string; color: string }> = {
  OK: { label: 'Đủ số đo', color: STATUS.good },
  MISSING_MEASUREMENT: { label: 'Thiếu số đo', color: STATUS.warning },
  SUSPECT_CAP: { label: 'Chạm trần thiết bị', color: STATUS.critical },
}

function pad(n: number) {
  return String(n).padStart(2, '0')
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

function StatusTile({ label, tone, status, hint }: { label: string; tone: Tone; status: string; hint?: string }) {
  return (
    <Paper withBorder p={{ base: 'md', sm: 'lg' }}>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Group gap={8} mt={8} wrap="nowrap">
        <Dot color={TONE[tone]} size={10} />
        <Text fw={650} fz={{ base: 17, sm: 20 }} lh={1.2}>
          {status}
        </Text>
      </Group>
      {hint && (
        <Text size="xs" c="dimmed" mt={6}>
          {hint}
        </Text>
      )}
    </Paper>
  )
}

type StatusRowProps = { q: QualitySummary | null; unreadable: boolean; dbUp: boolean | null }

function StatusRow({ q, unreadable, dbUp }: StatusRowProps) {
  const rec = q?.reconcile
  const keysUnique = q ? q.warehouse.distinct_keys === q.warehouse.fact_rows : false
  const aq = rec?.datasets[0]
  const dbt = q?.dbt_tests
  const run = q?.last_run
  // Summary not readable (API or database down): say so instead of "not run yet".
  const unknown = { tone: 'neutral' as const, status: 'Không rõ', hint: 'Không đọc được báo cáo' }
  return (
    <SimpleGrid cols={{ base: 2, lg: 4 }} spacing="md">
      <StatusTile
        label="Cơ sở dữ liệu"
        tone={dbUp == null ? 'neutral' : dbUp ? 'good' : 'critical'}
        status={dbUp == null ? 'Đang kiểm tra' : dbUp ? 'Đang chạy' : 'Mất kết nối'}
        hint="PostgreSQL · kiểm tra trực tiếp"
      />
      {unreadable || !q ? (
        <>
          <StatusTile label="Đối soát nạp dữ liệu" {...unknown} />
          <StatusTile label="dbt test" {...unknown} />
          <StatusTile label="Pipeline gần nhất" {...unknown} />
        </>
      ) : (
        <>
          <StatusTile
            label="Đối soát nạp dữ liệu"
            tone={!rec ? 'neutral' : rec.ok && keysUnique ? 'good' : 'critical'}
            status={!rec ? 'Chưa có' : rec.ok && keysUnique ? 'Khớp' : 'Lệch'}
            hint={aq ? `${fmtNum(aq.target_rows, 0)} / ${fmtNum(aq.source_rows, 0)} dòng` : 'Chưa chạy bước staging'}
          />
          <StatusTile
            label="dbt test"
            tone={!dbt ? 'neutral' : dbt.errors === 0 && dbt.passed === dbt.total ? 'good' : 'critical'}
            status={dbt ? `${dbt.passed}/${dbt.total} đạt` : 'Chưa có'}
            hint={dbt ? fmtWhen(dbt.finished_at) : undefined}
          />
          <StatusTile
            label="Pipeline gần nhất"
            tone={!run ? 'neutral' : run.ok ? 'good' : 'critical'}
            status={!run ? 'Chưa có' : run.ok ? 'Thành công' : `Lỗi ở bước ${failedStep(run)?.step ?? '?'}`}
            hint={run ? `${fmtWhen(run.finished_at)} · ${run.scope}` : undefined}
          />
        </>
      )}
    </SimpleGrid>
  )
}

/** Something an administrator should act on; nothing is shown when all is well. */
function Warnings({ q }: { q: QualitySummary }) {
  const notes: string[] = []
  const full = q.last_full_run
  if (full && !full.ok && full.finished_at !== q.last_run?.finished_at) {
    const step = failedStep(full)
    notes.push(
      `Lần chạy toàn bộ gần nhất (${fmtWhen(full.finished_at)}) lỗi ở bước ${step?.step ?? '?'}` +
        (step?.error ? `: ${step.error}` : '') +
        '. Dữ liệu hiện tại đến từ các lần chạy sau đó.',
    )
  }
  for (const err of q.reconcile?.errors ?? []) notes.push(`Đối soát: ${err}`)
  if (q.warehouse.distinct_keys !== q.warehouse.fact_rows) {
    notes.push(`Bảng sự kiện có ${fmtNum(q.warehouse.fact_rows - q.warehouse.distinct_keys, 0)} dòng trùng khoá (trạm, giờ).`)
  }
  if (!notes.length) return null
  return (
    <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={18} />} title="Cần chú ý">
      <Stack gap={4}>
        {notes.map((n) => (
          <Text key={n} size="sm">
            {n}
          </Text>
        ))}
      </Stack>
    </Alert>
  )
}

function Column({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack gap={8}>
      <Text size="xs" c="dimmed" fw={500}>
        {title}
      </Text>
      {children}
    </Stack>
  )
}

function SummaryPanel({ q }: { q: QualitySummary }) {
  const w = q.warehouse
  const rows = w.fact_rows || 1
  const flagsTotal = q.status_counts.reduce((s, c) => s + c.rows, 0) || 1
  const lastLoad = q.loads.reduce<string | null>(
    (latest, l) => (l.last_loaded_at && (!latest || l.last_loaded_at > latest) ? l.last_loaded_at : latest),
    null,
  )
  const pct = (n: number) => (n / rows) * 100
  const pollutants = q.columns.filter((c) => c.kind === 'Chất ô nhiễm')
  const weather = q.columns.filter((c) => c.kind === 'Thời tiết')
  const worst = pollutants.reduce((a, b) => (b.missing_at_source > a.missing_at_source ? b : a), pollutants[0])
  const range = (cols: typeof pollutants) => {
    const v = cols.map((c) => pct(c.missing_at_source))
    return `${fmtPct(Math.min(...v), v.some((x) => x < 1) ? 2 : 1)} – ${fmtPct(Math.max(...v), v.some((x) => x < 1) ? 2 : 1)}`
  }
  const weatherMissing = weather.reduce((s, c) => s + c.missing_at_source, 0)
  const weatherFilled = weather.reduce((s, c) => s + c.filled, 0)

  return (
    <Panel title="Tóm tắt">
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="xl">
        <Column title="Dữ liệu trong kho">
          <Text fz={26} fw={650} lh={1.1} className="tabular">
            {fmtNum(w.fact_rows, 0)}{' '}
            <Text span size="sm" c="dimmed" fw={400}>
              giờ-trạm
            </Text>
          </Text>
          <Text size="sm" c="dimmed">
            {fmtNum(w.stations, 0)} trạm · {fmtDay(w.first_hour)} – {fmtDay(w.last_hour)}
          </Text>
          <Text size="sm" c="dimmed">
            Nạp lần cuối {fmtWhen(lastLoad)}
          </Text>
        </Column>

        <Column title="Cờ chất lượng từng giờ">
          <Progress.Root size={14} radius="sm" mt={6}>
            {q.status_counts.map((c) => (
              <Progress.Section
                key={c.status}
                value={(c.rows / flagsTotal) * 100}
                color={FLAG[c.status]?.color ?? INK.muted}
              />
            ))}
          </Progress.Root>
          <Stack gap={4} mt={4}>
            {q.status_counts.map((c) => (
              <Group key={c.status} justify="space-between" wrap="nowrap">
                <Group gap={8} wrap="nowrap">
                  <Dot color={FLAG[c.status]?.color ?? INK.muted} size={8} />
                  <Text size="sm">{FLAG[c.status]?.label ?? c.status}</Text>
                </Group>
                <Text size="sm" className="tabular" c="dimmed">
                  {c.rows / flagsTotal < 0.001 ? `${fmtNum(c.rows, 0)} giờ` : fmtPct((c.rows / flagsTotal) * 100)}
                </Text>
              </Group>
            ))}
          </Stack>
        </Column>

        <Column title="Giá trị thiếu">
          <Text size="sm">
            <b>Chất ô nhiễm</b> thiếu {range(pollutants)} số giờ, nhiều nhất {worst?.label}. Giữ NULL, không nội suy.
          </Text>
          <Text size="sm">
            <b>Thời tiết</b> thiếu {range(weather)}, đã lấp{' '}
            {fmtPct(weatherMissing ? (weatherFilled / weatherMissing) * 100 : 100, 0)} từ Open-Meteo.
          </Text>
        </Column>
      </SimpleGrid>
    </Panel>
  )
}

export function QualityPage() {
  const [q, setQ] = useState<QualitySummary | null>(null)
  const [dbUp, setDbUp] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [round, setRound] = useState(0)

  useEffect(() => {
    let cancelled = false
    // Health on its own: if the database is down the summary fails, but this tile still says so.
    fetchDbHealth()
      .then(() => !cancelled && setDbUp(true))
      .catch(() => !cancelled && setDbUp(false))
    fetchQualitySummary(round > 0)
      .then((s) => {
        if (cancelled) return
        setQ(s)
        setError(null)
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [round])

  const recheck = () => {
    setLoading(true)
    setRound((r) => r + 1)
  }

  return (
    <Stack gap="lg">
      <PageHeader
        title="Chất lượng dữ liệu"
        description="Kho có đang chạy không, dữ liệu nạp vào có đủ và sạch không."
        actions={
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={recheck} loading={loading}>
            Kiểm tra lại
          </Button>
        }
      />
      {/* With the database down, a summary from cache would describe a state we cannot confirm. */}
      <StatusRow q={q} unreadable={(!q && !!error) || dbUp === false} dbUp={dbUp} />
      {error && <ErrorAlert title="Không đọc được báo cáo chất lượng" message={error} />}
      {!q && loading && <LoadingBlock height={140} />}
      {q && dbUp !== false && (
        <>
          <Warnings q={q} />
          <SummaryPanel q={q} />
        </>
      )}
    </Stack>
  )
}
