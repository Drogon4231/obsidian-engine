import { useEffect, useState } from 'preact/hooks'
import { computed } from '@preact/signals'
import {
  systemState, topic, stageNum, startedAt, logLines,
  isRunning, pipelineStatus, finishedAt, completionDismissed,
  lastRun, scheduleData, logPanelOpen, quickTriggerOpen, slideAgent,
  stageSummary, liveCostUsd,
} from '../state/store'
import { fetchLastRun, fetchScheduleData, triggerPipeline, fetchHistory, fetchLastError, fetchRunDetail } from '../state/api'
import type { LastErrorData } from '../state/api'
import { AGENTS } from '../data/agents'
import { StatsRow } from '../components/StatsRow'
import { StatusBadge } from '../components/StatusBadge'
import { EmptyState } from '../components/EmptyState'
import { showToast } from '../components/Toast'
import type { LastRunData, RunDetail } from '../types'

const visibleLog = computed(() => logLines.value.slice(-300))
const classifiedLog = computed(() =>
  visibleLog.value.map(line => {
    if (/STAGE\s+\d+/.test(line)) return { text: line, type: 'stage' as const }
    if (/ERROR|FAIL/i.test(line)) return { text: line, type: 'error' as const }
    if (/✓|SUCCESS/i.test(line)) return { text: line, type: 'success' as const }
    return { text: line, type: 'default' as const }
  })
)

const LOG_COLORS = { stage: 'text-cyan-400', error: 'text-error', success: 'text-success', default: 'text-text' }

export function HomeView() {
  const state = systemState.value
  const [historyItems, setHistoryItems] = useState<LastRunData[]>([])

  useEffect(() => {
    if (state === 'just-completed') {
      fetchLastRun().catch(() => {})
    }
    if (state === 'idle') {
      fetchScheduleData().catch(() => {})
      fetchHistory().then(h => setHistoryItems(h.slice(-3).reverse())).catch(() => {})
    }
  }, [state])

  // Elapsed timer during runs
  const [elapsed, setElapsed] = useState('')
  useEffect(() => {
    if (!isRunning.value || !startedAt.value) return
    const tick = () => {
      const start = new Date(startedAt.value!).getTime()
      const diff = Math.floor((Date.now() - start) / 1000)
      const m = Math.floor(diff / 60)
      const s = diff % 60
      setElapsed(`${m}m ${s}s`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [isRunning.value, startedAt.value])

  return (
    <div class="p-4 flex-1">
      <StatsRow />

      <div class="mt-6">
        {state === 'running' && <RunningState elapsed={elapsed} />}
        {state === 'just-completed' && <CompletedState />}
        {state === 'error' && <ErrorState />}
        {state === 'idle' && <IdleState historyItems={historyItems} />}
      </div>
    </div>
  )
}

function RunningState({ elapsed }: { elapsed: string }) {
  const agent = AGENTS.find(a => a.num === stageNum.value)
  const summary = stageSummary.value
  const [showRaw, setShowRaw] = useState(false)
  const [expandedStage, setExpandedStage] = useState<number | null>(null)

  // Stage telemetry summary strip
  const summaryParts: string[] = []
  if (summary['1']?.facts) summaryParts.push(`Research: ${summary['1'].facts} facts`)
  if (summary['4']?.words) summaryParts.push(`Script: ${Number(summary['4'].words).toLocaleString()} words`)
  if (summary['8']?.duration_s) summaryParts.push(`Audio: ${Math.floor(Number(summary['8'].duration_s) / 60)}m ${Number(summary['8'].duration_s) % 60}s`)
  if (summary['9']?.images_found) summaryParts.push(`Images: ${summary['9'].images_found}`)
  if (summary['10']?.generated) summaryParts.push(`Generated: ${summary['10'].passed_quality ?? summary['10'].generated}/${summary['10'].generated}`)

  return (
    <div class="flex gap-4">
      <div class="flex-1">
        {/* Run Banner */}
        <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4 mb-4">
          <div class="flex items-center gap-3 mb-2">
            <StatusBadge status="running" />
            <span class="text-bright font-bold">{topic.value}</span>
          </div>
          <div class="flex gap-4 text-sm text-dim">
            <span>Stage {stageNum.value}/13</span>
            <span>{agent?.codename ?? '...'}</span>
            <span>{elapsed}</span>
            {liveCostUsd.value != null && <span class="text-running">${liveCostUsd.value.toFixed(2)}</span>}
          </div>
        </div>

        {/* Stage Telemetry Summary Strip */}
        {summaryParts.length > 0 && (
          <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded px-4 py-2 mb-4 text-xs text-dim">
            {summaryParts.join(' | ')}
          </div>
        )}

        {/* DAG Progress */}
        <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4 mb-4">
          <div class="flex gap-2 flex-wrap">
            {AGENTS.map(a => {
              const done = a.num < stageNum.value
              const active = a.num === stageNum.value
              const parallel = isRunning.value && (stageNum.value === 8 || stageNum.value === 9) && (a.num === 8 || a.num === 9)
              const isActive = active || parallel
              return (
                <div
                  key={a.num}
                  class={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold
                    border transition-colors cursor-default
                    ${done ? 'bg-success/20 text-success border-success/40' :
                      isActive ? 'bg-running/20 text-running border-running/40 animate-pulse' :
                      'bg-bg-2 text-dim border-border'}`}
                  title={`${a.num}. ${a.codename}`}
                  aria-label={`Stage ${a.num}: ${a.codename}, ${done ? 'complete' : isActive ? 'active' : 'pending'}`}
                  onClick={() => { slideAgent.value = a.num }}
                  style={{ cursor: 'pointer' }}
                >
                  {a.num}
                </div>
              )
            })}
          </div>
        </div>

        {/* Agent Grid with expandable telemetry */}
        <div class="grid grid-cols-4 gap-2">
          {AGENTS.map(a => {
            const done = a.num < stageNum.value
            const active = a.num === stageNum.value
            const stageData = summary[String(a.num)]
            const expanded = expandedStage === a.num && stageData
            return (
              <div
                key={a.num}
                class={`backdrop-blur-sm bg-bg-1/80 border rounded p-2 text-xs cursor-pointer
                  ${active ? 'border-running/60' : done ? 'border-success/30' : 'border-border'}
                  ${expanded ? 'col-span-2 row-span-2' : ''}`}
                onClick={() => {
                  if (stageData) setExpandedStage(expandedStage === a.num ? null : a.num)
                  else slideAgent.value = a.num
                }}
              >
                <div class="text-dim text-[9px]">{a.num}</div>
                <div class={`font-bold ${active ? 'text-running' : done ? 'text-success' : 'text-dim'}`}>
                  {a.codename}
                </div>
                {/* Inline timing/cost if available */}
                {stageData?.timing_s != null && !expanded && (
                  <div class="text-[9px] text-dim mt-0.5">{Number(stageData.timing_s).toFixed(1)}s</div>
                )}
                {/* Expanded telemetry */}
                {expanded && (
                  <div class="mt-2 space-y-1 text-[10px]">
                    {Object.entries(stageData).map(([k, v]) => (
                      <div key={k} class="flex gap-1">
                        <span class="text-dim">{k.replace(/_/g, ' ')}:</span>
                        <span class="text-text">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* RAW toggle */}
        {Object.keys(summary).length > 0 && (
          <div class="mt-2">
            <button onClick={() => setShowRaw(!showRaw)} class="text-[10px] text-dim hover:text-text">
              {showRaw ? 'HIDE RAW' : 'RAW'}
            </button>
            {showRaw && (
              <pre class="mt-1 bg-bg-2 border border-border rounded p-2 text-[10px] text-text overflow-x-auto max-h-48">
                {JSON.stringify(summary, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Log Panel */}
      {logPanelOpen.value && (
        <div class="w-[285px] bg-bg-1 border border-border rounded p-3 overflow-y-auto max-h-[calc(100vh-200px)]">
          <div class="text-dim text-[10px] tracking-wider mb-2">LIVE LOG</div>
          <div class="font-mono text-[11px] space-y-0.5">
            {classifiedLog.value.map((line, i) => (
              <div key={i} class={LOG_COLORS[line.type]}>{line.text}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CompletedState() {
  const run = lastRun.value
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    fetchRunDetail().then(d => setDetail(d))
  }, [])

  return (
    <div class="space-y-4">
      <div class="backdrop-blur-sm bg-bg-1/80 border border-success/30 rounded p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="text-success text-2xl font-bold"
            style={{
              background: 'linear-gradient(90deg, var(--color-bright), var(--color-success), var(--color-bright))',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              color: 'transparent',
              backgroundSize: '200%',
              animation: 'shimmer 2s ease-in-out infinite',
            }}
          >
            DONE
          </span>
          <span class="text-bright font-bold">{run?.topic ?? topic.value}</span>
        </div>
        {run && (
          <div class="flex gap-4 text-sm text-dim mb-4">
            <span>{run.elapsed_seconds ? `${Math.floor(run.elapsed_seconds / 60)}m` : '—'}</span>
            {run.cost_usd != null && <span>${run.cost_usd.toFixed(2)}</span>}
            <span>{run.stages_completed}/13 stages</span>
          </div>
        )}
        <button
          onClick={() => {
            completionDismissed.value = finishedAt.value ?? ''
            try { localStorage.setItem('obsidian-cd', finishedAt.value ?? '') } catch {}
          }}
          class="px-3 py-1.5 text-xs text-dim border border-border rounded hover:text-bright"
        >
          Got it
        </button>
      </div>

      {/* Run Deep-Dive Forensics */}
      {detail && (
        <div class="space-y-3">
          {/* Cost Breakdown */}
          {detail.costs.usd_total > 0 && (
            <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3">
              <div class="text-dim text-[10px] tracking-wider mb-2">COST BREAKDOWN</div>
              <div class="flex gap-4 text-xs mb-2">
                <span class="text-bright font-bold">${detail.costs.usd_total.toFixed(2)} total</span>
              </div>
              {Object.keys(detail.costs.per_service).length > 0 && (
                <div class="space-y-1">
                  {Object.entries(detail.costs.per_service).map(([svc, cost]) => (
                    <div key={svc} class="flex items-center gap-2 text-[10px]">
                      <span class="text-dim w-20">{svc}</span>
                      <div class="flex-1 h-1.5 bg-bg-2 rounded overflow-hidden">
                        <div class="h-full bg-running/60 rounded" style={{ width: `${(cost / detail.costs.usd_total) * 100}%` }} />
                      </div>
                      <span class="text-text w-12 text-right">${cost.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Stage Timings */}
          {Object.keys(detail.stage_timings).length > 0 && (
            <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3">
              <div class="text-dim text-[10px] tracking-wider mb-2">STAGE TIMINGS</div>
              <div class="space-y-1">
                {Object.entries(detail.stage_timings).map(([stage, secs]) => {
                  const maxTime = Math.max(...Object.values(detail.stage_timings))
                  const a = AGENTS.find(ag => String(ag.num) === stage)
                  return (
                    <div key={stage} class="flex items-center gap-2 text-[10px]">
                      <span class="text-dim w-24 truncate">{a?.codename ?? `Stage ${stage}`}</span>
                      <div class="flex-1 h-1.5 bg-bg-2 rounded overflow-hidden">
                        <div class="h-full bg-success/60 rounded" style={{ width: `${(secs / maxTime) * 100}%` }} />
                      </div>
                      <span class="text-text w-12 text-right">{secs.toFixed(1)}s</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Quality Scorecard */}
          {Object.keys(detail.quality).length > 0 && (
            <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3">
              <div class="text-dim text-[10px] tracking-wider mb-2">QUALITY GATES</div>
              <div class="grid grid-cols-3 gap-2 text-xs">
                {detail.quality.fact_verification && (
                  <QualityGate label="Fact Check" value={detail.quality.fact_verification} pass={detail.quality.fact_verification === 'APPROVED'} />
                )}
                {detail.quality.compliance && (
                  <QualityGate label="Compliance" value={detail.quality.compliance.risk_level} pass={detail.quality.compliance.risk_level === 'green'} />
                )}
                {detail.quality.seo_score != null && (
                  <QualityGate label="SEO Score" value={String(detail.quality.seo_score)} pass={detail.quality.seo_score >= 70} />
                )}
                {detail.quality.qa_tier2_sync_pct != null && (
                  <QualityGate label="Audio Sync" value={`${detail.quality.qa_tier2_sync_pct.toFixed(1)}%`} pass={detail.quality.qa_tier2_sync_pct >= 90} />
                )}
                {detail.quality.predictive_score != null && (
                  <QualityGate label="Prediction" value={detail.quality.predictive_score.toFixed(1)} pass={detail.quality.predictive_score >= 6} />
                )}
                {detail.quality.script_doctor && (
                  <QualityGate label="Script Doctor" value={Object.values(detail.quality.script_doctor)[0]?.toFixed(2) ?? '—'} pass={true} />
                )}
              </div>
            </div>
          )}

          {/* Agent Performance */}
          {detail.agent_performance.length > 0 && (
            <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3">
              <div class="text-dim text-[10px] tracking-wider mb-2">AGENT PERFORMANCE</div>
              <div class="overflow-x-auto">
                <table class="w-full text-[10px]">
                  <thead>
                    <tr class="text-dim border-b border-border">
                      <th class="text-left p-1">Agent</th>
                      <th class="text-right p-1">Time</th>
                      <th class="text-right p-1">SLA</th>
                      <th class="text-left p-1">Model</th>
                      <th class="text-left p-1">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.agent_performance.map((ap, i) => (
                      <tr key={i} class="border-b border-border/30">
                        <td class="p-1 text-text">{ap.agent}</td>
                        <td class={`p-1 text-right ${ap.elapsed_s > ap.sla_s ? 'text-error' : 'text-success'}`}>
                          {ap.elapsed_s.toFixed(1)}s
                        </td>
                        <td class="p-1 text-right text-dim">{ap.sla_s}s</td>
                        <td class="p-1 text-dim">{ap.model}</td>
                        <td class={`p-1 ${ap.status === 'success' ? 'text-success' : 'text-error'}`}>{ap.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* RAW toggle */}
          <button onClick={() => setShowRaw(!showRaw)} class="text-[10px] text-dim hover:text-text">
            {showRaw ? 'HIDE RAW' : 'RAW'}
          </button>
          {showRaw && (
            <pre class="bg-bg-2 border border-border rounded p-2 text-[10px] text-text overflow-x-auto max-h-60">
              {JSON.stringify(detail, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

function QualityGate({ label, value, pass }: { label: string; value: string; pass: boolean }) {
  return (
    <div class={`backdrop-blur-sm bg-bg-2 border rounded p-2 text-center ${pass ? 'border-success/30' : 'border-error/30'}`}>
      <div class="text-dim text-[9px]">{label}</div>
      <div class={`font-bold text-sm ${pass ? 'text-success' : 'text-error'}`}>{value}</div>
    </div>
  )
}

function ErrorState() {
  const lastLines = logLines.value.slice(-5)
  const [diagnosis, setDiagnosis] = useState<LastErrorData | null>(null)

  useEffect(() => {
    fetchLastError().then(d => setDiagnosis(d))
  }, [])

  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-error/30 rounded p-6">
      <div class="flex items-center gap-3 mb-3">
        <StatusBadge status={pipelineStatus.value} />
        <span class="text-bright font-bold">{topic.value}</span>
      </div>
      <div class="text-sm text-dim mb-2">Failed at stage {stageNum.value}</div>

      {/* Pipeline Doctor diagnosis */}
      {diagnosis && (
        <div class="bg-bg-2 border border-border rounded p-3 mb-4 space-y-2 text-xs">
          <div class="text-dim text-[10px] tracking-wider">PIPELINE DOCTOR DIAGNOSIS</div>
          <div class="flex gap-2">
            <span class="text-dim min-w-[70px]">Stage</span>
            <span class="text-bright">{diagnosis.stage_name} (#{diagnosis.stage_num})</span>
          </div>
          {diagnosis.diagnosis && (
            <div class="flex gap-2">
              <span class="text-dim min-w-[70px]">Diagnosis</span>
              <span class="text-text">{diagnosis.diagnosis}</span>
            </div>
          )}
          {diagnosis.root_cause && (
            <div class="flex gap-2">
              <span class="text-dim min-w-[70px]">Root Cause</span>
              <span class="text-text">{diagnosis.root_cause}</span>
            </div>
          )}
          {diagnosis.strategy && (
            <div class="flex gap-2">
              <span class="text-dim min-w-[70px]">Strategy</span>
              <span class="text-running">{diagnosis.strategy}</span>
            </div>
          )}
        </div>
      )}

      {/* Fallback: raw log lines */}
      {!diagnosis && (
        <div class="bg-bg-2 rounded p-3 mb-4 text-[11px] font-mono text-error">
          {lastLines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}

      <div class="flex gap-2">
        <button
          onClick={async () => {
            try {
              await triggerPipeline(topic.value, stageNum.value)
              showToast(`Retrying from stage ${stageNum.value}`)
            } catch {
              showToast('Failed to retry', 'error')
            }
          }}
          class="px-3 py-1.5 text-xs text-running border border-running/30 rounded hover:bg-running/10"
        >
          Retry from Stage {stageNum.value}
        </button>
        <button
          onClick={() => { location.hash = 'health' }}
          class="px-3 py-1.5 text-xs text-dim border border-border rounded hover:text-text"
        >
          Health View
        </button>
      </div>
    </div>
  )
}

function IdleState({ historyItems }: { historyItems: LastRunData[] }) {
  const schedule = scheduleData.value

  return (
    <div>
      {/* CTA */}
      <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4 mb-4 flex items-center justify-between">
        <div>
          <div class="text-bright text-sm font-bold">Ready to fire</div>
          <div class="text-dim text-xs mt-1">Press T to quick-fire a topic</div>
        </div>
        <button
          onClick={() => { quickTriggerOpen.value = true }}
          class="px-4 py-2 text-sm font-bold bg-running/20 text-running border border-running/30 rounded hover:bg-running/30"
        >
          FIRE
        </button>
      </div>

      {/* Recent runs */}
      {historyItems.length > 0 ? (
        <div class="space-y-2 mb-4">
          <div class="text-dim text-[10px] tracking-wider">RECENT RUNS</div>
          {historyItems.map((h, i) => (
            <div key={i} class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3 flex items-center gap-3">
              {h.youtube_id && (
                <a href={`https://youtube.com/watch?v=${h.youtube_id}`} target="_blank" rel="noopener noreferrer">
                  <img
                    src={`https://img.youtube.com/vi/${h.youtube_id}/mqdefault.jpg`}
                    class="rounded border border-border"
                    width={80}
                    alt={`Thumbnail: ${h.topic}`}
                  />
                </a>
              )}
              <StatusBadge status={h.status} />
              <span class="text-sm text-bright flex-1">{h.topic}</span>
              <div class="flex flex-col items-end gap-0.5">
                {h.cost_usd != null && <span class="text-xs text-dim">${h.cost_usd.toFixed(2)}</span>}
                {h.elapsed_seconds > 0 && <span class="text-[10px] text-dim">{Math.floor(h.elapsed_seconds / 60)}m</span>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Welcome. Add a topic to get started.">
          <span>Go to <a href="#queue" class="text-running underline">Queue</a> or press T</span>
        </EmptyState>
      )}

      {/* Schedule */}
      {schedule && schedule.length > 0 && (
        <div class="text-dim text-xs mt-4">
          Next: {schedule[0]?.job} ({schedule[0]?.day} {schedule[0]?.time_utc} UTC)
        </div>
      )}
    </div>
  )
}
