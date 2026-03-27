import type { VNode } from 'preact'

interface BarDatum {
  label: string
  value: number
  color?: string
}

interface TooltipData { x: number; y: number; label: string; value: string }

export function renderBars(
  data: BarDatum[],
  width: number,
  height: number,
  onHover: (d: TooltipData | null) => void
): VNode[] {
  if (!data.length) return []
  const pad = { top: 10, right: 10, bottom: 30, left: 40 }
  const w = width - pad.left - pad.right
  const h = height - pad.top - pad.bottom
  const max = Math.max(...data.map(d => d.value), 1)
  const barW = Math.max(4, Math.min(40, w / data.length - 4))

  const bars = data.map((d, i) => {
    const x = pad.left + (w / data.length) * i + (w / data.length - barW) / 2
    const barH = (d.value / max) * h
    const y = pad.top + h - barH
    return (
      <g key={i}>
        <rect
          x={x} y={y} width={barW} height={barH}
          fill={d.color || 'var(--color-running)'}
          rx={2}
          opacity={0.8}
          onMouseEnter={() => onHover({ x, y, label: d.label, value: d.value.toLocaleString() })}
          onMouseLeave={() => onHover(null)}
        />
        {barW > 12 && (
          <text x={x + barW / 2} y={height - 8} text-anchor="middle" fill="var(--color-dim)" font-size="9">
            {d.label.slice(0, 6)}
          </text>
        )}
      </g>
    )
  })

  // Y-axis ticks
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => {
    const val = Math.round(max * t)
    const y = pad.top + h - h * t
    return (
      <g key={`t${t}`}>
        <line x1={pad.left - 4} y1={y} x2={pad.left + w} y2={y} stroke="var(--color-border)" stroke-width={0.5} />
        <text x={pad.left - 6} y={y + 3} text-anchor="end" fill="var(--color-dim)" font-size="9">{val}</text>
      </g>
    )
  })

  return [...ticks, ...bars]
}
