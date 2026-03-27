import type { VNode } from 'preact'

interface HBarDatum {
  label: string
  value: number
  color?: string
}

interface TooltipData { x: number; y: number; label: string; value: string }

export function renderHBars(
  data: HBarDatum[],
  width: number,
  height: number,
  onHover: (d: TooltipData | null) => void
): VNode[] {
  if (!data.length) return []
  const pad = { top: 5, right: 10, bottom: 5, left: 80 }
  const w = width - pad.left - pad.right
  const h = height - pad.top - pad.bottom
  const max = Math.max(...data.map(d => d.value), 1)
  const barH = Math.max(4, Math.min(24, h / data.length - 4))

  return data.map((d, i) => {
    const y = pad.top + (h / data.length) * i + (h / data.length - barH) / 2
    const barW = (d.value / max) * w
    return (
      <g key={i}>
        <text x={pad.left - 6} y={y + barH / 2 + 3} text-anchor="end" fill="var(--color-dim)" font-size="10">
          {d.label.slice(0, 12)}
        </text>
        <rect
          x={pad.left} y={y} width={Math.max(2, barW)} height={barH}
          fill={d.color || 'var(--color-running)'}
          rx={2}
          opacity={0.8}
          onMouseEnter={() => onHover({ x: pad.left + barW, y, label: d.label, value: d.value.toLocaleString() })}
          onMouseLeave={() => onHover(null)}
        />
        <text x={pad.left + barW + 6} y={y + barH / 2 + 3} fill="var(--color-text)" font-size="10">
          {d.value.toLocaleString()}
        </text>
      </g>
    )
  })
}
