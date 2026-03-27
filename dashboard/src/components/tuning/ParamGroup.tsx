import { useState } from 'preact/hooks'
import type { ParamBound } from '../../types'
import { ParamSlider } from './ParamSlider'

interface Props {
  label: string
  params: ParamBound[]
  defaultExpanded?: boolean
}

export function ParamGroup({ label, params, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (params.length === 0) return null

  return (
    <div class="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        class="flex items-center gap-2 w-full text-left"
      >
        <span class="text-dim text-[10px] tracking-wider uppercase font-bold">{label}</span>
        <span class="text-[10px] text-dim bg-bg-2 px-1.5 py-0.5 rounded">{params.length}</span>
        <div class="flex-1 border-b border-border/50" />
        <span class="text-dim text-xs">{expanded ? '\u25BE' : '\u25B8'}</span>
      </button>
      {expanded && (
        <div class="space-y-5 pl-1">
          {params.map(p => <ParamSlider key={p.key} param={p} />)}
        </div>
      )}
    </div>
  )
}
