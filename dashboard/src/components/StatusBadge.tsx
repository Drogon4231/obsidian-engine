import type { PipelineStatus } from '../types'

const STATUS_STYLES: Record<string, string> = {
  idle: 'bg-dim/20 text-dim',
  running: 'bg-running/20 text-running',
  done: 'bg-success/20 text-success',
  failed: 'bg-error/20 text-error',
  error: 'bg-error/20 text-error',
  killed: 'bg-warning/20 text-warning',
}

interface Props {
  status: PipelineStatus | string
}

export function StatusBadge({ status }: Props) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES['idle']
  return (
    <span class={`inline-block px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${style}`}>
      {status}
    </span>
  )
}
