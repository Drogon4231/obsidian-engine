import type { VNode } from 'preact'

interface StackedDatum {
  label: string
  segments: { key: string; value: number; color: string }[]
}

interface TooltipData { x: number; y: number; label: string; value: string }

const STACK_COLORS = [
  'var(--color-running)', 'var(--color-success)', 'var(--color-warning)',
  'var(--color-error)', '#8b5cf6', '#06b6d4',
]

export function renderStacked(
  data: StackedDatum[],
  width: number,
  height: number,
  onHover: (d: TooltipData | null) => void
): VNode[] {
  if (!data.length) return []
  const pad = { top: 10, right: 10, bottom: 30, left: 40 }
  const w = width - pad.left - pad.right
  const h = height - pad.top - pad.bottom
  const maxTotal = Math.max(...data.map(d => d.segments.reduce((s, seg) => s + seg.value, 0)), 1)
  const barW = Math.max(4, Math.min(40, w / data.length - 4))

  const bars = data.map((d, i) => {
    const x = pad.left + (w / data.length) * i + (w / data.length - barW) / 2
    let cumY = pad.top + h
    const segs = d.segments.map((seg, si) => {
      const segH = (seg.value / maxTotal) * h
      cumY -= segH
      return (
        <rect
          key={`${i}-${si}`}
          x={x} y={cumY} width={barW} height={segH}
          fill={seg.color || STACK_COLORS[si % STACK_COLORS.length]}
          rx={si === d.segments.length - 1 ? 2 : 0}
          opacity={0.8}
          onMouseEnter={() => onHover({ x, y: cumY, label: `${d.label} — ${seg.key}`, value: seg.value.toLocaleString() })}
          onMouseLeave={() => onHover(null)}
        />
      )
    })
    return (
      <g key={i}>
        {segs}
        {barW > 12 && (
          <text x={x + barW / 2} y={height - 8} text-anchor="middle" fill="var(--color-dim)" font-size="9">
            {d.label.slice(0, 6)}
          </text>
        )}
      </g>
    )
  })

  return bars
}
