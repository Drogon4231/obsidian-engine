import { queueDepth, errors24h, healthStatus, lastCostUsd, pulseHistory } from '../state/store'
import { MetricCard } from './MetricCard'

export function StatsRow() {
  const h = pulseHistory.value
  return (
    <div class="flex gap-3 flex-wrap" aria-live="polite">
      <MetricCard label="Queue" value={queueDepth.value} trend={h.queue} />
      <MetricCard label="Errors (24h)" value={errors24h.value} trend={h.errors} />
      <MetricCard label="Health" value={healthStatus.value} />
      <MetricCard
        label="Last Cost"
        value={lastCostUsd.value !== null ? `$${lastCostUsd.value.toFixed(2)}` : '—'}
        trend={h.cost}
      />
    </div>
  )
}
