import type { ComponentChildren } from 'preact'

interface Props {
  title: string
  children?: ComponentChildren
}

export function EmptyState({ title, children }: Props) {
  return (
    <div class="flex flex-col items-center justify-center py-16 text-center">
      <p class="text-dim text-lg mb-2">{title}</p>
      {children && <div class="text-dim text-sm">{children}</div>}
    </div>
  )
}
