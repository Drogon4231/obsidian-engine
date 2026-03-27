import { useState } from 'preact/hooks'
import type { OverrideHistoryEntry } from '../../types'
import { PARAM_BY_KEY } from '../../data/params'

interface Props {
  history: OverrideHistoryEntry[]
}

function relativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function OverrideHistory({ history }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded">
      <button
        onClick={() => setExpanded(!expanded)}
        class="w-full flex items-center justify-between p-3 text-sm text-bright hover:text-white"
      >
        <span class="flex items-center gap-2">
          Override History
          {history.length > 0 && (
            <span class="text-[10px] text-dim bg-bg-2 px-1.5 py-0.5 rounded">{history.length}</span>
          )}
        </span>
        <span class="text-dim">{expanded ? '\u25BE' : '\u25B8'}</span>
      </button>
      {expanded && (
        <div class="px-3 pb-3">
          {history.length === 0 ? (
            <div class="text-dim text-xs">No overrides recorded yet</div>
          ) : (
            <div class="overflow-x-auto">
              <table class="w-full text-xs">
                <thead>
                  <tr class="text-dim border-b border-border">
                    <th class="text-left p-1.5">Parameter</th>
                    <th class="text-left p-1.5">Action</th>
                    <th class="text-right p-1.5">Value</th>
                    <th class="text-right p-1.5">Previous</th>
                    <th class="text-right p-1.5">When</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 20).map((entry, i) => {
                    const param = PARAM_BY_KEY[entry.key]
                    return (
                      <tr key={i} class="border-b border-border/30">
                        <td class="p-1.5 text-text">{param?.label ?? entry.key}</td>
                        <td class="p-1.5">
                          <span class={entry.action === 'approve' ? 'text-success' : 'text-warning'}>
                            {entry.action.toUpperCase()}
                          </span>
                        </td>
                        <td class="p-1.5 text-right text-bright tabular-nums">
                          {entry.value != null ? entry.value.toFixed(2) : '-'}
                        </td>
                        <td class="p-1.5 text-right text-dim tabular-nums">
                          {entry.previous_value != null ? entry.previous_value.toFixed(2) : '-'}
                        </td>
                        <td class="p-1.5 text-right text-dim" title={entry.timestamp}>
                          {relativeTime(entry.timestamp)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
