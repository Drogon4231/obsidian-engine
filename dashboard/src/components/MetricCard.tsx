interface Props {
  label: string
  value: number | string
  trend?: number[] // last 6+ values for sparkline + trend arrow
}

function computeTrend(data: number[]): '↑' | '↓' | '→' {
  if (data.length < 6) return '→'
  const recent = data.slice(-3)
  const prior = data.slice(-6, -3)
  const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length
  const priorAvg = prior.reduce((a, b) => a + b, 0) / prior.length
  if (recentAvg > priorAvg * 1.05) return '↑'
  if (recentAvg < priorAvg * 0.95) return '↓'
  return '→'
}

const TREND_COLORS = { '↑': 'text-success', '↓': 'text-error', '→': 'text-dim' }

export function MetricCard({ label, value, trend }: Props) {
  const arrow = trend ? computeTrend(trend) : null

  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3 min-w-[140px]">
      <div class="text-dim text-[10px] tracking-wider uppercase mb-1">{label}</div>
      <div class="text-bright text-xl font-bold flex items-center gap-2">
        <span>{value}</span>
        {arrow && <span class={`text-sm ${TREND_COLORS[arrow]}`}>{arrow}</span>}
      </div>
      {trend && trend.length >= 2 && (
        <svg class="mt-1" width="80" height="16" viewBox="0 0 80 16">
          <polyline
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            class="text-dim"
            points={trend.map((v, i) => {
              const x = (i / (trend.length - 1)) * 78 + 1
              const max = Math.max(...trend, 1)
              const y = 15 - (v / max) * 14
              return `${x},${y}`
            }).join(' ')}
          />
        </svg>
      )}
    </div>
  )
}
