import { useState, useEffect } from 'preact/hooks'
import { intelCache } from '../state/store'
import { fetchDashboard } from '../state/api'
import { Skeleton } from '../components/Skeleton'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { Chart } from '../components/Chart'
import { renderBars } from '../components/renderers/BarRenderer'
import { renderHBars } from '../components/renderers/HBarRenderer'
import type { SummarySignal } from '../types'

const TABS = ['summary', 'performance', 'content', 'audience', 'config'] as const
type Tab = typeof TABS[number]

export function IntelView() {
  const [tab, setTab] = useState<Tab>('summary')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (intelCache.value[tab] === undefined) {
      setLoading(true)
      fetchDashboard(tab)
        .catch(() => {})
        .finally(() => setLoading(false))
    }
  }, [tab])

  const data = intelCache.value[tab]

  return (
    <div class="p-4">
      {/* Sub-tabs */}
      <div class="flex gap-1 mb-4">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            class={`px-3 py-1.5 text-xs tracking-wider rounded
              ${tab === t ? 'bg-bg-2 text-bright border border-border' : 'text-dim hover:text-text'}`}
          >
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      <ErrorBoundary>
        {loading ? (
          <div class="space-y-3">
            <Skeleton height="2rem" />
            <Skeleton height="4rem" />
            <Skeleton height="4rem" />
          </div>
        ) : !data ? (
          <div class="text-dim text-sm">No data available</div>
        ) : tab === 'summary' ? (
          <SummaryTab data={data as { signals: SummarySignal[] }} />
        ) : tab === 'performance' ? (
          <PerformanceTab data={data as Record<string, unknown>} />
        ) : tab === 'content' ? (
          <ContentTab data={data as Record<string, unknown>} />
        ) : tab === 'audience' ? (
          <AudienceTab data={data as Record<string, unknown>} />
        ) : tab === 'config' ? (
          <ConfigTab data={data as Record<string, unknown>} />
        ) : (
          <GenericSection data={data as Record<string, unknown>} />
        )}
      </ErrorBoundary>
    </div>
  )
}

function SummaryTab({ data }: { data: { signals: SummarySignal[] } }) {
  const signals = data?.signals ?? []
  const TYPE_COLORS: Record<string, string> = {
    info: 'border-running/30',
    success: 'border-success/30',
    warning: 'border-warning/30',
    error: 'border-error/30',
    neutral: 'border-border',
  }

  return (
    <div class="space-y-3">
      {signals.map((s, i) => (
        <div key={i} class={`backdrop-blur-sm bg-bg-1/80 border rounded p-3 ${TYPE_COLORS[s.type] ?? 'border-border'}`}>
          <div class="text-dim text-[10px] tracking-wider">{s.label}</div>
          <div class="text-bright text-sm mt-1">{s.value}</div>
        </div>
      ))}
    </div>
  )
}

function PerformanceTab({ data }: { data: Record<string, unknown> }) {
  const videoStats = asArray(data.per_video_stats)
  const eraPerf = data.era_performance as Record<string, unknown> | undefined
  const retention = data.retention_analysis as Record<string, unknown> | undefined

  return (
    <div class="space-y-4">
      {/* Per-video bar chart */}
      {videoStats.length > 0 && (
        <DataCard title="PER VIDEO PERFORMANCE">
          <Chart
            height={200}
            renderer={(w, h, onHover) =>
              renderBars(
                videoStats.slice(0, 20).map(v => ({
                  label: (v as Record<string, unknown>).title as string ?? '',
                  value: Number((v as Record<string, unknown>).views ?? 0),
                  color: 'var(--color-running)',
                })),
                w, h, onHover
              )
            }
          />
        </DataCard>
      )}

      {/* Retention line chart */}
      {retention && (
        <DataCard title="RETENTION ANALYSIS">
          <GenericKV data={retention} />
        </DataCard>
      )}

      {/* Era performance */}
      {eraPerf && (
        <DataCard title="ERA PERFORMANCE">
          <Chart
            height={180}
            renderer={(w, h, onHover) =>
              renderHBars(
                Object.entries(eraPerf).map(([era, val]) => ({
                  label: era,
                  value: Number((val as Record<string, unknown>)?.avg_views ?? val ?? 0),
                })),
                w, h, onHover
              )
            }
          />
        </DataCard>
      )}

      {Object.keys(data).length === 0 && <div class="text-dim text-sm">No performance data available</div>}
    </div>
  )
}

function ContentTab({ data }: { data: Record<string, unknown> }) {
  const tagPerf = data.tag_performance as Record<string, number> | undefined
  const topVideos = asArray(data.top_performing_videos)

  return (
    <div class="space-y-4">
      {/* Tag performance horizontal bars */}
      {tagPerf && Object.keys(tagPerf).length > 0 && (
        <DataCard title="TAG PERFORMANCE">
          <Chart
            height={Math.min(300, Object.keys(tagPerf).length * 28 + 20)}
            renderer={(w, h, onHover) =>
              renderHBars(
                Object.entries(tagPerf)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 10)
                  .map(([tag, val]) => ({ label: tag, value: val, color: 'var(--color-success)' })),
                w, h, onHover
              )
            }
          />
        </DataCard>
      )}

      {/* Top videos as a list */}
      {topVideos.length > 0 && (
        <ExpandableList title="TOP PERFORMING VIDEOS" items={topVideos} limit={5} />
      )}

      {/* Remaining data sections */}
      {Object.entries(data)
        .filter(([k]) => !['tag_performance', 'top_performing_videos'].includes(k))
        .map(([key, val]) => (
          <DataCard key={key} title={key.replace(/_/g, ' ').toUpperCase()}>
            <GenericKV data={val as Record<string, unknown>} />
          </DataCard>
        ))}
    </div>
  )
}

function AudienceTab({ data }: { data: Record<string, unknown> }) {
  const requests = asArray(data.audience_requests)

  return (
    <div class="space-y-4">
      {requests.length > 0 && (
        <DataCard title="AUDIENCE REQUESTS">
          <Chart
            height={Math.min(250, requests.length * 28 + 20)}
            renderer={(w, h, onHover) =>
              renderHBars(
                requests.slice(0, 8).map(r => ({
                  label: String((r as Record<string, unknown>).topic ?? r),
                  value: Number((r as Record<string, unknown>).count ?? 1),
                  color: 'var(--color-warning)',
                })),
                w, h, onHover
              )
            }
          />
        </DataCard>
      )}

      {Object.entries(data)
        .filter(([k]) => k !== 'audience_requests')
        .map(([key, val]) => (
          <DataCard key={key} title={key.replace(/_/g, ' ').toUpperCase()}>
            {typeof val === 'object' && val !== null && !Array.isArray(val)
              ? <GenericKV data={val as Record<string, unknown>} />
              : <pre class="text-[11px] text-text overflow-x-auto max-h-60">{JSON.stringify(val, null, 2)}</pre>}
          </DataCard>
        ))}
    </div>
  )
}

function DataCard({ title, children }: { title: string; children: preact.ComponentChildren }) {
  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3">
      <div class="text-dim text-[10px] tracking-wider mb-2">{title}</div>
      {children}
    </div>
  )
}

function GenericKV({ data }: { data: Record<string, unknown> }) {
  return (
    <div class="space-y-1 text-xs">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} class="flex gap-2">
          <span class="text-dim min-w-[100px]">{k.replace(/_/g, ' ')}</span>
          <span class="text-text">
            {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}
          </span>
        </div>
      ))}
    </div>
  )
}

function GenericSection({ data }: { data: Record<string, unknown> }) {
  return (
    <div class="space-y-4">
      {Object.entries(data).map(([key, val]) => (
        <DataCard key={key} title={key.replace(/_/g, ' ').toUpperCase()}>
          <pre class="text-[11px] text-text overflow-x-auto max-h-60">
            {typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val)}
          </pre>
        </DataCard>
      ))}
    </div>
  )
}

function ExpandableList({ title, items, limit }: { title: string; items: unknown[]; limit: number }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? items : items.slice(0, limit)

  return (
    <DataCard title={title}>
      <div class="space-y-1.5">
        {visible.map((item, i) => {
          const obj = item as Record<string, unknown>
          return (
            <div key={i} class="flex items-center gap-2 text-xs">
              <span class="text-dim w-4">{i + 1}.</span>
              <span class="text-bright flex-1 truncate">{String(obj.title ?? obj.topic ?? JSON.stringify(item))}</span>
              {obj.views != null && <span class="text-dim">{Number(obj.views).toLocaleString()} views</span>}
            </div>
          )
        })}
      </div>
      {items.length > limit && (
        <button
          onClick={() => setExpanded(!expanded)}
          class="text-running text-[10px] mt-2 hover:underline"
        >
          {expanded ? 'Show less' : `Show all ${items.length}`}
        </button>
      )}
    </DataCard>
  )
}

function ConfigTab({ data }: { data: Record<string, unknown> }) {
  const weights = (data.scoring_weights ?? data.scoring_adjustments) as Record<string, Record<string, number>> | undefined
  const thresholds = data.quality_thresholds as Record<string, number> | undefined
  const remaining = Object.entries(data).filter(
    ([k]) => !['scoring_weights', 'scoring_adjustments', 'quality_thresholds'].includes(k)
  )

  return (
    <div class="space-y-4">
      {/* Scoring Weights Table */}
      {weights && Object.keys(weights).length > 0 && (
        <DataCard title="SCORING WEIGHTS">
          <div class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-dim border-b border-border">
                  <th class="text-left p-1">Factor</th>
                  {Object.keys(Object.values(weights)[0] ?? {}).map(tier => (
                    <th key={tier} class="text-right p-1 capitalize">{tier}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(weights).map(([factor, tiers]) => (
                  <tr key={factor} class="border-b border-border/30">
                    <td class="p-1 text-text">{factor.replace(/_/g, ' ')}</td>
                    {Object.values(tiers).map((v, i) => (
                      <td key={i} class="p-1 text-right text-bright">{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DataCard>
      )}

      {/* Quality Thresholds */}
      {thresholds && Object.keys(thresholds).length > 0 && (
        <DataCard title="QUALITY THRESHOLDS">
          <div class="space-y-1 text-xs">
            {Object.entries(thresholds).map(([k, v]) => (
              <div key={k} class="flex items-center gap-2">
                <span class="text-dim flex-1">{k.replace(/_/g, ' ')}</span>
                <span class={`font-bold ${v >= 0.8 ? 'text-success' : v >= 0.5 ? 'text-warning' : 'text-error'}`}>
                  {typeof v === 'number' ? v.toFixed(2) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </DataCard>
      )}

      {/* Remaining config sections */}
      {remaining.map(([key, val]) => (
        <DataCard key={key} title={key.replace(/_/g, ' ').toUpperCase()}>
          {typeof val === 'object' && val !== null && !Array.isArray(val)
            ? <GenericKV data={val as Record<string, unknown>} />
            : <pre class="text-[11px] text-text overflow-x-auto max-h-60">{JSON.stringify(val, null, 2)}</pre>}
        </DataCard>
      ))}

      {Object.keys(data).length === 0 && <div class="text-dim text-sm">No config data available</div>}
    </div>
  )
}

function asArray(val: unknown): unknown[] {
  return Array.isArray(val) ? val : []
}
