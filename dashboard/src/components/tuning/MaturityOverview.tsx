import type { CorrelationResults, CorrelationLayer } from '../../types'
import { LAYER_DEFS } from '../../data/params'

interface Props {
  correlation: CorrelationResults
}

const MATURITY_COLORS: Record<string, string> = {
  early: 'bg-dim/20 text-dim',
  emerging: 'bg-warning/20 text-warning',
  established: 'bg-running/20 text-running',
  mature: 'bg-success/20 text-success',
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-success/20 text-success border-success/30',
  insufficient_data: 'bg-warning/20 text-warning border-warning/30',
  inactive: 'bg-bg-2 text-dim border-border',
}

export function MaturityOverview({ correlation }: Props) {
  const maturity = correlation.maturity ?? 'early'
  const layers = correlation.layers ?? {}

  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4">
      <div class="flex items-center gap-3 mb-3">
        <span class="text-dim text-[10px] tracking-wider">DATA MATURITY</span>
        <span class={`text-[10px] font-bold px-2 py-0.5 rounded ${MATURITY_COLORS[maturity] ?? MATURITY_COLORS.early}`}>
          {maturity.toUpperCase()}
        </span>
        {correlation.video_count != null && (
          <span class="text-dim text-[10px]">{correlation.video_count} videos, {correlation.short_count ?? 0} shorts</span>
        )}
      </div>

      {correlation.maturity_description && (
        <div class="text-xs text-text mb-3">{correlation.maturity_description}</div>
      )}

      <div class="text-dim text-[10px] tracking-wider mb-2">CORRELATION LAYERS</div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {LAYER_DEFS.map(def => {
          const layer = layers[String(def.id)] as CorrelationLayer | undefined
          const status = layer?.status ?? 'inactive'
          const colorCls = STATUS_COLORS[status] ?? STATUS_COLORS.inactive
          return (
            <div key={def.id} class={`border rounded p-2.5 ${colorCls}`}>
              <div class="flex items-center gap-1.5 mb-1">
                <span class="text-[9px] text-dim">L{def.id}</span>
                <span class="text-xs text-bright font-bold truncate">{def.name}</span>
              </div>
              <div class="text-[9px] text-dim">{def.phase}</div>
              <div class="text-[9px] text-dim mt-1 leading-tight">
                {layer?.reason ?? def.requirement}
              </div>
            </div>
          )
        })}
      </div>

      <div class="text-dim text-[9px] mt-3 italic">
        With weekly video cadence, expect 3-6 videos before directional signals emerge.
      </div>
    </div>
  )
}
