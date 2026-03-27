import type { TuningRecommendation } from '../../types'
import { PARAM_BY_KEY, formatParamValue } from '../../data/params'

interface Props {
  recommendations: TuningRecommendation[]
}

const CONFIDENCE_COLORS: Record<string, string> = {
  strong: 'bg-success/20 text-success border-success/30',
  moderate: 'bg-running/20 text-running border-running/30',
  directional: 'bg-warning/20 text-warning border-warning/30',
  weak: 'bg-dim/20 text-dim border-border',
}

export function Recommendations({ recommendations }: Props) {
  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4">
      <div class="text-dim text-[10px] tracking-wider mb-3">RECOMMENDATIONS</div>

      {recommendations.length === 0 ? (
        <div class="text-dim text-xs py-4 text-center">
          Awaiting parameter variation -- adjust some parameters manually to begin data collection
        </div>
      ) : (
        <div class="space-y-3">
          {recommendations.map((rec, i) => {
            const param = PARAM_BY_KEY[rec.parameter_key]
            const colorCls = CONFIDENCE_COLORS[rec.confidence] ?? CONFIDENCE_COLORS.weak
            return (
              <div key={i} class={`border rounded p-3 ${colorCls}`}>
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-xs text-bright font-bold">{param?.label ?? rec.parameter_key}</span>
                  <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-bg-2/50">
                    {rec.confidence.toUpperCase()}
                  </span>
                </div>
                <div class="text-sm text-bright font-bold mb-1">
                  {param ? formatParamValue(rec.suggested_value, param) : rec.suggested_value.toFixed(3)}
                </div>
                <div class="text-[10px] text-text">{rec.interpretation}</div>
                {rec.quality_score != null && (
                  <div class="mt-2 h-1.5 bg-bg-2 rounded-full overflow-hidden">
                    <div
                      class="h-full bg-running/60 rounded-full"
                      style={{ width: `${rec.quality_score * 100}%` }}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
