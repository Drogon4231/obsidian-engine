import type { VNode } from 'preact'

interface LineDatum {
  label: string
  value: number
}

interface TooltipData { x: number; y: number; label: string; value: string }

export function renderLine(
  data: LineDatum[],
  width: number,
  height: number,
  onHover: (d: TooltipData | null) => void,
  color = 'var(--color-running)'
): VNode[] {
  if (data.length < 2) return []
  const pad = { top: 10, right: 10, bottom: 25, left: 40 }
  const w = width - pad.left - pad.right
  const h = height - pad.top - pad.bottom
  const max = Math.max(...data.map(d => d.value), 1)
  const min = Math.min(...data.map(d => d.value), 0)
  const range = max - min || 1

  const points = data.map((d, i) => ({
    x: pad.left + (i / (data.length - 1)) * w,
    y: pad.top + h - ((d.value - min) / range) * h,
    datum: d,
  }))

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  const areaPath = `${linePath} L${points[points.length - 1]!.x},${pad.top + h} L${points[0]!.x},${pad.top + h} Z`

  const ticks = [0, 0.5, 1].map(t => {
    const val = Math.round(min + range * t)
    const y = pad.top + h - h * t
    return (
      <g key={`t${t}`}>
        <line x1={pad.left} y1={y} x2={pad.left + w} y2={y} stroke="var(--color-border)" stroke-width={0.5} />
        <text x={pad.left - 6} y={y + 3} text-anchor="end" fill="var(--color-dim)" font-size="9">{val}</text>
      </g>
    )
  })

  const dots = points.map((p, i) => (
    <circle
      key={`d${i}`}
      cx={p.x} cy={p.y} r={3}
      fill={color} opacity={0}
      onMouseEnter={() => onHover({ x: p.x, y: p.y, label: p.datum.label, value: p.datum.value.toLocaleString() })}
      onMouseLeave={() => onHover(null)}
    >
      <set attributeName="opacity" to="1" begin="mouseenter" end="mouseleave" />
    </circle>
  ))

  return [
    ...ticks,
    <path key="area" d={areaPath} fill={color} opacity={0.1} />,
    <path key="line" d={linePath} fill="none" stroke={color} stroke-width={2} />,
    ...dots,
  ]
}
