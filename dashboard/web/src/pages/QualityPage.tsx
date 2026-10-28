import { Badge, Button, Group, Paper, Progress, SimpleGrid, Stack, Table, Text, Tooltip } from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { fetchDbHealth, fetchQualitySummary, type PipelineRun, type QualitySummary } from '../api/quality'
import { Metric } from '../components/Metric'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { Dot } from '../components/Pm25Badge'
import { ErrorAlert, LoadingBlock } from '../components/States'
import { fmtNum, fmtPct } from '../format'
import { INK, STATUS } from '../theme'

type Tone = 'good' | 'warning' | 'critical' | 'neutral'
const TONE: Record<Tone, string> = {
  good: STATUS.good,
  warning: STATUS.warning,
  critical: STATUS.critical,
  neutral: INK.muted,
}

// Data-quality flag set when the hour is cleaned (see docs/DATA_PREPROCESSING.md).
const FLAG: Record<string, { label: string; color: string }> = {
  OK: { label: 'Đủ số đo', color: STATUS.good },
  MISSING_MEASUREMENT: {
    label: 'Thiếu số đo (giữ NULL)',
    color: STATUS.warning,
  },
  SUSPECT_CAP: { label: 'Nghi chạm trần thiết bị', color: STATUS.critical },
}

const SOURCE: Record<string, string> = {
  uci_prsa: 'File CSV UCI',
  operational_db: 'CSDL vận hành (CDC)',
}

// Step names and what they do, as scripts/run_all.py prints them.
const STEP: Record<string, string> = {
  prereq: 'Kiểm tra Python/Docker, .env',
  download: 'Tải bộ dữ liệu UCI (12 CSV)',
  infra: 'Docker: PostgreSQL + MinIO',
  lake: 'CSV → MinIO → Parquet',
  openmeteo: 'Thời tiết Open-Meteo',
  staging: 'Nạp staging + đối soát',
  warehouse: 'dbt: lược đồ sao, khối con',
  clustering: 'Phân cụm trạm',
  forecast: 'Ma trận đặc trưng + hồi quy',
  classify: 'Phân loại cảnh báo',
  dbt_test: 'dbt test',
  checks: 'Đối chiếu mart với artifact',
  olap: 'Kiểm chứng OLAP + notebook',
  dashboard: 'Dashboard API',
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

type StatusRowProps = {
  q: QualitySummary | null
  unreadable: boolean
  dbUp: boolean | null
  checkedAt: Date | null
}

function StatusRow({ q, unreadable, dbUp, checkedAt }: StatusRowProps) {
  const rec = q?.reconcile
  const keysUnique = q ? q.warehouse.distinct_keys === q.warehouse.fact_rows : false
  const aq = rec?.datasets[0]
  const dbt = q?.dbt_tests
  const run = q?.last_run
  const failed = run ? failedStep(run) : undefined
  // Summary not readable (API or database down): say so instead of "not run yet".
  const unknown = {
    tone: 'neutral' as const,
    status: 'Không rõ',
    hint: 'Không đọc được báo cáo',
  }
  return (
    <SimpleGrid cols={{ base: 2, lg: 4 }} spacing="md">
      <StatusTile
        label="Cơ sở dữ liệu"
        tone={dbUp == null ? 'neutral' : dbUp ? 'good' : 'critical'}
        status={dbUp == null ? 'Đang kiểm tra' : dbUp ? 'Đang chạy' : 'Mất kết nối'}
        hint={
          checkedAt
            ? `Kiểm tra lúc ${pad(checkedAt.getHours())}:${pad(checkedAt.getMinutes())}:${pad(checkedAt.getSeconds())}`
            : undefined
        }
      />
      {unreadable ? (
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
            hint={
              aq
                ? `${fmtNum(aq.target_rows, 0)} / ${fmtNum(aq.source_rows, 0)} dòng · ${keysUnique ? 'không trùng khoá' : 'có khoá trùng'}`
                : 'Chưa chạy bước staging'
            }
          />
          <StatusTile
            label="dbt test"
            tone={!dbt ? 'neutral' : dbt.errors === 0 && dbt.passed === dbt.total ? 'good' : 'critical'}
            status={dbt ? `${dbt.passed}/${dbt.total} đạt` : 'Chưa có'}
            hint={dbt ? `Chạy lúc ${fmtWhen(dbt.finished_at)}` : undefined}
          />
          <StatusTile
            label="Pipeline gần nhất"
            tone={!run ? 'neutral' : run.ok ? 'good' : 'critical'}
            status={!run ? 'Chưa có' : run.ok ? 'Thành công' : `Lỗi ở bước ${failed?.step ?? '?'}`}
            hint={run ? `${fmtWhen(run.finished_at)} · ${run.scope}` : undefined}
          />
        </>
      )}
    </SimpleGrid>
  )
}

function WarehousePanel({ q }: { q: QualitySummary }) {
  const w = q.warehouse
  return (
    <Panel
      title="Dữ liệu trong kho"
      description="Bảng sự kiện dwh.fact_air_quality_hourly: mỗi dòng là một trạm trong một giờ."
    >
      <SimpleGrid cols={3} spacing="md">
        <Metric
          label="Số dòng"
          value={fmtNum(w.fact_rows, 0)}
          hint={`${fmtDay(w.first_hour)} – ${fmtDay(w.last_hour)}`}
          size="sm"
        />
        <Metric label="Trạm" value={fmtNum(w.stations, 0)} size="sm" />
        <Metric label="Khoá trùng" value={fmtNum(w.fact_rows - w.distinct_keys, 0)} hint="(trạm, giờ)" size="sm" />
      </SimpleGrid>
      <Text size="xs" c="dimmed" mt="lg" mb={6}>
        Lần nạp gần nhất (staging.load_registry) · nguồn:{' '}
        {q.sources.map((s) => `${SOURCE[s.source_system] ?? s.source_system} ${fmtNum(s.rows, 0)} dòng`).join(', ')}
      </Text>
      <Table.ScrollContainer minWidth={460}>
        <Table verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Bộ dữ liệu</Table.Th>
              <Table.Th ta="right">File</Table.Th>
              <Table.Th ta="right">Số dòng</Table.Th>
              <Table.Th ta="right">Nạp lúc</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {q.loads.map((l) => (
              <Table.Tr key={l.dataset}>
                <Table.Td>{l.dataset}</Table.Td>
                <Table.Td ta="right" className="tabular">
                  {fmtNum(l.files, 0)}
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {fmtNum(l.rows, 0)}
                </Table.Td>
                <Table.Td ta="right" className="tabular" style={{ whiteSpace: 'nowrap' }}>
                  {fmtWhen(l.last_loaded_at)}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Panel>
  )
}

function FlagsPanel({ q }: { q: QualitySummary }) {
  const total = q.status_counts.reduce((s, c) => s + c.rows, 0)
  return (
    <Panel
      title="Cờ chất lượng từng giờ"
      description="Gắn cho mỗi dòng khi làm sạch; dòng có cờ vẫn được giữ trong kho."
    >
      <Progress.Root size={18} radius="sm">
        {q.status_counts.map((c) => (
          <Tooltip key={c.status} label={`${FLAG[c.status]?.label ?? c.status}: ${fmtNum(c.rows, 0)} giờ`}>
            <Progress.Section value={(c.rows / total) * 100} color={FLAG[c.status]?.color ?? INK.muted} />
          </Tooltip>
        ))}
      </Progress.Root>
      <Stack gap={10} mt="lg">
        {q.status_counts.map((c) => (
          <Group key={c.status} justify="space-between" wrap="nowrap">
            <Group gap={8} wrap="nowrap">
              <Dot color={FLAG[c.status]?.color ?? INK.muted} size={10} />
              <Text size="sm">{FLAG[c.status]?.label ?? c.status}</Text>
              <Text size="xs" c="dimmed" visibleFrom="sm">
                {c.status}
              </Text>
            </Group>
            <Text size="sm" className="tabular" style={{ whiteSpace: 'nowrap' }}>
              <b>{fmtNum(c.rows, 0)}</b>{' '}
              <Text span size="xs" c="dimmed">
                ({fmtPct((c.rows / total) * 100, c.rows / total < 0.001 ? 3 : 1)})
              </Text>
            </Text>
          </Group>
        ))}
      </Stack>
      <Text size="xs" c="dimmed" mt="lg">
        Giờ thiếu số đo vẫn nằm trong kho để chuỗi thời gian không bị đứt; khai phá tự loại hoặc điền theo cách xử lý ở
        bảng dưới. SUSPECT_CAP: giá trị đúng bằng trần thiết bị (PM2.5, PM10 = 999; CO = 10000).
      </Text>
    </Panel>
  )
}

function MissingPanel({ q }: { q: QualitySummary }) {
  const rows = q.warehouse.fact_rows || 1
  return (
    <Panel
      title="Giá trị thiếu theo cột"
      description="Thiếu ở nguồn = còn thiếu trong kho + đã lấp từ Open-Meteo. Chất ô nhiễm không được nội suy."
    >
      <Table.ScrollContainer minWidth={720}>
        <Table verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Cột</Table.Th>
              <Table.Th ta="right">Thiếu ở nguồn</Table.Th>
              <Table.Th ta="right">Đã lấp</Table.Th>
              <Table.Th ta="right">Còn thiếu trong kho</Table.Th>
              <Table.Th>Cách xử lý</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {q.columns.map((c) => (
              <Table.Tr key={c.column}>
                <Table.Td style={{ whiteSpace: 'nowrap' }}>
                  <Text size="sm" fw={500}>
                    {c.label}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {c.kind}
                  </Text>
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {fmtNum(c.missing_at_source, 0)}{' '}
                  <Text span size="xs" c="dimmed">
                    ({fmtPct((c.missing_at_source / rows) * 100, 2)})
                  </Text>
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {c.filled ? fmtNum(c.filled, 0) : '—'}
                </Table.Td>
                <Table.Td ta="right" className="tabular" fw={c.remaining ? 600 : 400}>
                  {fmtNum(c.remaining, 0)}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {c.treatment}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Panel>
  )
}

function PipelinePanel({ run, full }: { run: PipelineRun; full: PipelineRun | null }) {
  const fullFailed = full ? failedStep(full) : undefined
  const showFull = full && full.finished_at !== run.finished_at
  return (
    <Panel
      title="Lần chạy pipeline gần nhất"
      description={`python scripts/run_all.py · ${run.scope} · xong lúc ${fmtWhen(run.finished_at)}${
        run.total_seconds ? ` · ${fmtNum(run.total_seconds / 60, 1)} phút` : ''
      }`}
    >
      <Table.ScrollContainer minWidth={340}>
        <Table verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Bước</Table.Th>
              <Table.Th>Trạng thái</Table.Th>
              <Table.Th ta="right">Thời gian</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {run.steps.map((s) => (
              <Table.Tr key={s.step}>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {STEP[s.step] ?? s.step}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {s.step}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={s.status === 'ok' ? 'green' : s.status === 'skipped' ? 'gray' : 'red'}>
                    {s.status === 'ok' ? 'Xong' : s.status === 'skipped' ? 'Bỏ qua' : 'Lỗi'}
                  </Badge>
                  {s.error && (
                    <Text size="xs" c="red.7" mt={4}>
                      {s.error}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {s.seconds == null ? '—' : `${fmtNum(s.seconds, 1)} giây`}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {showFull && full && (
        <Group gap={8} mt="md" wrap="nowrap" align="flex-start">
          <Dot color={full.ok ? STATUS.good : STATUS.critical} size={10} />
          <Text size="sm">
            Lần chạy toàn bộ gần nhất ({fmtWhen(full.finished_at)}):{' '}
            {full.ok ? (
              `thành công${full.total_seconds ? `, ${fmtNum(full.total_seconds / 60, 1)} phút` : ''}.`
            ) : (
              <>
                lỗi ở bước <b>{fullFailed?.step ?? '?'}</b>
                {fullFailed?.error ? ` (${fullFailed.error})` : ''}.
              </>
            )}
          </Text>
        </Group>
      )}
    </Panel>
  )
}

export function QualityPage() {
  const [q, setQ] = useState<QualitySummary | null>(null)
  const [dbUp, setDbUp] = useState<boolean | null>(null)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [round, setRound] = useState(0)

  useEffect(() => {
    let cancelled = false
    // Health first and on its own: if the database is down, the summary fails but the tile
    // still says so.
    fetchDbHealth()
      .then(() => !cancelled && setDbUp(true))
      .catch(() => !cancelled && setDbUp(false))
      .finally(() => !cancelled && setCheckedAt(new Date()))
    fetchQualitySummary()
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
        description="Kho có đang chạy không, dữ liệu nạp vào có đủ và sạch không, và lần chạy pipeline gần nhất ra sao."
        actions={
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={recheck} loading={loading}>
            Kiểm tra lại
          </Button>
        }
      />
      <StatusRow q={q} unreadable={!q && !!error} dbUp={dbUp} checkedAt={checkedAt} />
      {error && <ErrorAlert title="Không đọc được báo cáo chất lượng" message={error} />}
      {!q && loading && <LoadingBlock height={240} />}
      {q && (
        <>
          <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
            <WarehousePanel q={q} />
            <FlagsPanel q={q} />
          </SimpleGrid>
          <MissingPanel q={q} />
          {q.last_run && <PipelinePanel run={q.last_run} full={q.last_full_run} />}
        </>
      )}
    </Stack>
  )
}
