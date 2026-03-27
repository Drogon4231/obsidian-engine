interface Props {
  class?: string
  width?: string
  height?: string
}

export function Skeleton({ class: cls = '', width = '100%', height = '1rem' }: Props) {
  return (
    <div
      class={`animate-pulse bg-bg-2 rounded ${cls}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  )
}
