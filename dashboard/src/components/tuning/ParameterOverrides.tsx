import { PARAM_DEFS, PARAM_GROUPS } from '../../data/params'
import { ParamGroup } from './ParamGroup'

export function ParameterOverrides() {
  const grouped = PARAM_GROUPS.map(g => ({
    ...g,
    params: PARAM_DEFS.filter(p => p.group === g.id),
  }))

  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4">
      <div class="mb-1">
        <span class="text-dim text-[10px] tracking-wider">PARAMETER TUNING</span>
      </div>
      <div class="text-[10px] text-dim mb-4">
        Adjust audio and pacing parameters. Changes are saved to your override bank.
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Long-form on left */}
        <div class="space-y-4">
          {grouped.filter(g => g.id === 'long_form').map(g => (
            <ParamGroup key={g.id} label={g.label} params={g.params} defaultExpanded={true} />
          ))}
        </div>

        {/* Shorts on right */}
        <div class="space-y-4">
          {grouped.filter(g => g.id !== 'long_form').map(g => (
            <ParamGroup key={g.id} label={g.label} params={g.params} />
          ))}
        </div>
      </div>
    </div>
  )
}
