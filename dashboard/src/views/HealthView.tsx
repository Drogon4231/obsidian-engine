import { useEffect, useState } from 'preact/hooks'
import { isRunning, stageNum, healthStatus, errors24h, errorSummary, agentStats } from '../state/store'
import { fetchErrorSummary, fetchAgentStats } from '../state/api'
import { AGENTS } from '../data/agents'
import { Skeleton } from '../components/Skeleton'

interface MusicData {
  total_tracks?: number
  tracks_by_mood?: Record<string, number>
  [k: string]: unknown
}

interface TrendData {
  trends?: { topic: string; fetched_at?: string; score?: number }[]
  [k: string]: unknown
}

interface AuditData {
  entries?: { file?: string; status?: string; reason?: string }[]
  [k: string]: unknown
}

interface ScheduleData {
  schedule?: { job: string; day: string; time_utc: string }[]
  [k: string]: unknown
}

export function HealthView() {
  const [music, setMusic] = useState<MusicData | null>(null)
  const [trends, setTrends] = useState<TrendData | null>(null)
  const [audit, setAudit] = useState<AuditData | null>(null)
  const [schedule, setSchedule] = useState<ScheduleData | null>(null)
  const [expandedPanels, setExpandedPanels] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const key = typeof window !== 'undefined' ? window.__TRIGGER_KEY__ : ''
    const headers = { 'X-Trigger-Key': key }
    fetch('/music', { headers }).then(r => r.json()).then(setMusic).catch(() => {})
    fetch('/trends', { headers }).then(r => r.json()).then(setTrends).catch(() => {})
    fetch('/audit', { headers }).then(r => r.json()).then(setAudit).catch(() => {})
    fetch('/schedule', { headers }).then(r => r.json()).then(setSchedule).catch(() => {})
  }, [])

  const toggle = (key: string) => setExpandedPanels(p => ({ ...p, [key]: !p[key] }))

  return (
    <div class="p-4">
      {/* Health Summary */}
      <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4 mb-4">
        <div class="text-bright text-sm font-bold mb-2">System Health</div>
        <div class="flex gap-4 text-sm">
          <span class={healthStatus.value === 'healthy' ? 'text-success' : healthStatus.value === 'degraded' ? 'text-warning' : 'text-error'}>
            {healthStatus.value.toUpperCase()}
          </span>
          <span class="text-dim">{errors24h.value} errors (24h)</span>
        </div>
      </div>

      {/* Live Status during runs */}
      {isRunning.value && (
        <div class="backdrop-blur-sm bg-bg-1/80 border border-running/30 rounded p-4 mb-4">
          <div class="text-running text-sm font-bold mb-2">Live Status</div>
          <div class="text-sm text-dim">
            Active: Stage {stageNum.value} — {AGENTS.find(a => a.num === stageNum.value)?.codename ?? '...'}
          </div>
        </div>
      )}

      {/* Agent Performance Table */}
      <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4 mb-4 overflow-x-auto">
        <div class="text-dim text-[10px] tracking-wider mb-2">AGENT PERFORMANCE</div>
        <table class="w-full text-xs">
          <thead>
            <tr class="text-dim border-b border-border">
              <th class="text-left p-1">#</th>
              <th class="text-left p-1">Agent</th>
              <th class="text-left p-1">Codename</th>
            </tr>
          </thead>
          <tbody>
            {AGENTS.map(a => (
              <tr key={a.num} class="border-b border-border/30">
                <td class="p-1 text-dim">{a.num}</td>
                <td class="p-1 text-text">{a.name}</td>
                <td class="p-1 text-bright">{a.codename}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Systems Panels */}
      <div class="space-y-2">
        <CollapsiblePanel
          title="Music Library"
          expanded={expandedPanels['music'] ?? false}
          onToggle={() => toggle('music')}
          badge={music?.total_tracks != null ? `${music.total_tracks} tracks` : undefined}
        >
          {music ? <MusicPanel data={music} /> : <Skeleton height="3rem" />}
        </CollapsiblePanel>

        <CollapsiblePanel
          title="Trend Detection"
          expanded={expandedPanels['trends'] ?? false}
          onToggle={() => toggle('trends')}
          badge={trends?.trends ? `${trends.trends.length} trends` : undefined}
        >
          {trends ? <TrendsPanel data={trends} /> : <Skeleton height="3rem" />}
        </CollapsiblePanel>

        <CollapsiblePanel
          title="Image Audit"
          expanded={expandedPanels['audit'] ?? false}
          onToggle={() => toggle('audit')}
          badge={audit?.entries ? `${audit.entries.length} entries` : undefined}
        >
          {audit ? <AuditPanel data={audit} /> : <Skeleton height="3rem" />}
        </CollapsiblePanel>

        <CollapsiblePanel
          title="Schedule"
          expanded={expandedPanels['schedule'] ?? false}
          onToggle={() => toggle('schedule')}
          badge={schedule?.schedule ? `${schedule.schedule.length} jobs` : undefined}
        >
          {schedule ? <SchedulePanel data={schedule} /> : <Skeleton height="3rem" />}
        </CollapsiblePanel>

        <CollapsiblePanel
          title="Error Log"
          expanded={expandedPanels['errors'] ?? false}
          onToggle={() => toggle('errors')}
          badge={errorSummary.value ? `${errorSummary.value.length} groups` : undefined}
        >
          <ErrorLogPanel />
        </CollapsiblePanel>

        <CollapsiblePanel
          title="Agent Performance"
          expanded={expandedPanels['agent-perf'] ?? false}
          onToggle={() => toggle('agent-perf')}
        >
          <AgentPerfPanel />
        </CollapsiblePanel>

        <CollapsiblePanel
          title="Cost Breakdown"
          expanded={expandedPanels['cost'] ?? false}
          onToggle={() => toggle('cost')}
        >
          <CostPanel />
        </CollapsiblePanel>
      </div>
    </div>
  )
}

function CollapsiblePanel({ title, expanded, onToggle, badge, children }: {
  title: string; expanded: boolean; onToggle: () => void; badge?: string; children: preact.ComponentChildren
}) {
  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded">
      <button
        onClick={onToggle}
        class="w-full flex items-center justify-between p-3 text-sm text-bright hover:text-white"
      >
        <span class="flex items-center gap-2">
          {title}
          {badge && <span class="text-[10px] text-dim bg-bg-2 px-1.5 py-0.5 rounded">{badge}</span>}
        </span>
        <span class="text-dim">{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded && <div class="px-3 pb-3">{children}</div>}
    </div>
  )
}

function MusicPanel({ data }: { data: MusicData }) {
  const moods = data.tracks_by_mood ?? {}
  const moodEntries = Object.entries(moods).sort(([, a], [, b]) => (b as number) - (a as number))

  return (
    <div>
      <div class="text-sm text-dim mb-2">Total: <span class="text-bright">{data.total_tracks ?? 0}</span> tracks</div>
      {moodEntries.length > 0 && (
        <div class="space-y-1">
          {moodEntries.map(([mood, count]) => {
            const pct = data.total_tracks ? ((count as number) / data.total_tracks) * 100 : 0
            return (
              <div key={mood} class="flex items-center gap-2 text-xs">
                <span class="w-20 text-dim capitalize">{mood}</span>
                <div class="flex-1 h-2 bg-bg-2 rounded overflow-hidden">
                  <div class="h-full bg-running/60 rounded" style={{ width: `${pct}%` }} />
                </div>
                <span class="text-dim w-8 text-right">{count as number}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function trendRecencyColor(fetchedAt?: string): string {
  if (!fetchedAt) return 'text-dim'
  const days = (Date.now() - new Date(fetchedAt).getTime()) / 86_400_000
  if (days < 7) return 'text-success'
  if (days < 30) return 'text-warning'
  return 'text-dim'
}

function trendRecencyLabel(fetchedAt?: string): string {
  if (!fetchedAt) return '(stale)'
  const days = (Date.now() - new Date(fetchedAt).getTime()) / 86_400_000
  if (days < 7) return '(recent)'
  if (days < 30) return '(aging)'
  return '(stale)'
}

function TrendsPanel({ data }: { data: TrendData }) {
  const trendList = data.trends ?? []
  if (!trendList.length) return <div class="text-dim text-xs">No trends detected</div>

  return (
    <div class="space-y-1">
      {trendList.map((t, i) => (
        <div key={i} class="flex items-center gap-2 text-xs">
          <span class={`w-2 h-2 rounded-full ${trendRecencyColor(t.fetched_at).replace('text-', 'bg-')}`} />
          <span class={`flex-1 ${trendRecencyColor(t.fetched_at)}`}>{t.topic}</span>
          <span class="text-dim text-[10px]">{trendRecencyLabel(t.fetched_at)}</span>
          {t.score != null && <span class="text-dim">{t.score.toFixed(1)}</span>}
        </div>
      ))}
    </div>
  )
}

function AuditPanel({ data }: { data: AuditData }) {
  const entries = data.entries ?? []
  if (!entries.length) return <div class="text-dim text-xs">No audit entries</div>

  return (
    <div class="space-y-1 max-h-48 overflow-y-auto">
      {entries.map((e, i) => (
        <div key={i} class="flex items-center gap-2 text-xs">
          <span class={e.status === 'pass' ? 'text-success' : e.status === 'fail' ? 'text-error' : 'text-warning'}>
            {e.status === 'pass' ? '\u2713' : e.status === 'fail' ? '\u2717' : '\u26A0'}
          </span>
          <span class="text-text flex-1 truncate">{e.file ?? 'unknown'}</span>
          {e.reason && <span class="text-dim truncate max-w-[200px]">{e.reason}</span>}
        </div>
      ))}
    </div>
  )
}

function SchedulePanel({ data }: { data: ScheduleData }) {
  const jobs = data.schedule ?? []
  const [, setTick] = useState(0)

  // Re-render every minute for live countdown
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 60000)
    return () => clearInterval(id)
  }, [])

  if (!jobs.length) return <div class="text-dim text-xs">No scheduled jobs</div>

  return (
    <div class="space-y-1">
      {jobs.map((j, i) => {
        const countdown = computeCountdown(j.day, j.time_utc)
        return (
          <div key={i} class="flex items-center gap-3 text-xs">
            <span class="text-bright flex-1">{j.job}</span>
            <span class="text-dim">{j.day} {j.time_utc} UTC</span>
            {countdown && <span class="text-running">{countdown}</span>}
          </div>
        )
      })}
    </div>
  )
}

function ErrorLogPanel() {
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    if (!loaded) {
      fetchErrorSummary().finally(() => setLoaded(true))
    }
  }, [loaded])

  const errors = errorSummary.value ?? []
  if (!errors.length) return <div class="text-dim text-xs">No errors in last 24h</div>

  return (
    <div class="space-y-1 max-h-60 overflow-y-auto">
      {errors.map((e, i) => (
        <div key={i} class="flex items-center gap-2 text-xs">
          <span class={e.severity === 'critical' ? 'text-error' : 'text-warning'}>
            {e.count}x
          </span>
          <span class="text-bright flex-1 truncate">{e.agent}</span>
          <span class="text-dim truncate max-w-[200px]">{e.error_type}</span>
        </div>
      ))}
    </div>
  )
}

function AgentPerfPanel() {
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    if (!loaded) {
      fetchAgentStats().finally(() => setLoaded(true))
    }
  }, [loaded])

  const stats = agentStats.value ?? []
  if (!stats.length) return <div class="text-dim text-xs">No agent data yet</div>

  return (
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-dim border-b border-border">
            <th class="text-left p-1">Agent</th>
            <th class="text-right p-1">Calls</th>
            <th class="text-right p-1">Avg (s)</th>
            <th class="text-right p-1">P95 (s)</th>
            <th class="text-right p-1">Success</th>
            <th class="text-right p-1">SLA Miss</th>
          </tr>
        </thead>
        <tbody>
          {stats.map((s, i) => (
            <tr key={i} class="border-b border-border/30">
              <td class="p-1 text-bright truncate max-w-[120px]">{s.agent}</td>
              <td class="p-1 text-dim text-right">{s.calls}</td>
              <td class="p-1 text-text text-right">{s.avg_latency}</td>
              <td class="p-1 text-text text-right">{s.p95_latency}</td>
              <td class={`p-1 text-right ${s.success_rate >= 95 ? 'text-success' : s.success_rate >= 80 ? 'text-warning' : 'text-error'}`}>
                {s.success_rate}%
              </td>
              <td class={`p-1 text-right ${s.sla_breach_rate <= 5 ? 'text-dim' : 'text-warning'}`}>
                {s.sla_breach_rate}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CostPanel() {
  const stats = agentStats.value ?? []
  if (!stats.length) return <div class="text-dim text-xs">No cost data yet</div>

  // Approximate cost from token usage (display relative token consumption)
  const sorted = [...stats].sort((a, b) =>
    (b.avg_input_tokens + b.avg_output_tokens) * b.calls -
    (a.avg_input_tokens + a.avg_output_tokens) * a.calls
  )
  const first = sorted[0]
  const maxTokens = first
    ? (first.avg_input_tokens + first.avg_output_tokens) * first.calls
    : 1

  return (
    <div class="space-y-1">
      {sorted.slice(0, 10).map((s, i) => {
        const total = (s.avg_input_tokens + s.avg_output_tokens) * s.calls
        const pct = maxTokens > 0 ? (total / maxTokens) * 100 : 0
        return (
          <div key={i} class="flex items-center gap-2 text-xs">
            <span class="w-28 text-dim truncate">{s.agent}</span>
            <div class="flex-1 h-2 bg-bg-2 rounded overflow-hidden">
              <div class="h-full bg-running/60 rounded" style={{ width: `${pct}%` }} />
            </div>
            <span class="text-dim w-16 text-right">{(total / 1000).toFixed(0)}k tok</span>
          </div>
        )
      })}
    </div>
  )
}

function computeCountdown(day: string, timeUtc: string): string | null {
  try {
    const upper = day.toUpperCase()
    const now = new Date()

    // Handle "3H" — every 3 hours
    if (upper === '3H') {
      const currentH = now.getUTCHours()
      const nextSlot = (Math.floor(currentH / 3) + 1) * 3
      const target = new Date(now)
      if (nextSlot >= 24) {
        target.setUTCDate(target.getUTCDate() + 1)
        target.setUTCHours(0, 0, 0, 0)
      } else {
        target.setUTCHours(nextSlot, 0, 0, 0)
      }
      const diff = target.getTime() - now.getTime()
      const hours = Math.floor(diff / 3_600_000)
      const mins = Math.floor((diff % 3_600_000) / 60_000)
      return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
    }

    // Handle "DAILY" — next occurrence at timeUtc today or tomorrow
    if (upper === 'DAILY') {
      const [h, m] = timeUtc.split(':').map(Number)
      if (h == null || m == null) return null
      const target = new Date(now)
      target.setUTCHours(h, m, 0, 0)
      if (target.getTime() <= now.getTime()) {
        target.setUTCDate(target.getUTCDate() + 1)
      }
      const diff = target.getTime() - now.getTime()
      const hours = Math.floor(diff / 3_600_000)
      const mins = Math.floor((diff % 3_600_000) / 60_000)
      return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
    }

    // Weekday-based schedule
    const ABBREV: Record<string, string> = {
      SUN: 'Sunday', MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
      THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday',
    }
    const normalizedDay = ABBREV[upper] ?? day
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    const targetDay = days.indexOf(normalizedDay)
    if (targetDay === -1) return null
    const [h, m] = timeUtc.split(':').map(Number)
    if (h == null || m == null) return null

    const nowDay = now.getUTCDay()
    const daysUntil = (targetDay - nowDay + 7) % 7
    const target = new Date(now)
    target.setUTCDate(now.getUTCDate() + daysUntil)
    target.setUTCHours(h, m, 0, 0)
    if (target.getTime() <= now.getTime()) {
      target.setUTCDate(target.getUTCDate() + 7)
    }
    const diff = target.getTime() - now.getTime()
    const hours = Math.floor(diff / 3_600_000)
    const mins = Math.floor((diff % 3_600_000) / 60_000)
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
  } catch {
    return null
  }
}
