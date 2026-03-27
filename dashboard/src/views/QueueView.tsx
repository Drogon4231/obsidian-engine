import { useEffect, useState } from 'preact/hooks'
import { fetchQueue, addToQueue, deleteFromQueue } from '../state/api'
import { EmptyState } from '../components/EmptyState'
import { showToast } from '../components/Toast'

interface QueueItem {
  id: string
  topic: string
  status: string
  score: number
  source: string
  [k: string]: unknown
}

type SortKey = 'topic' | 'score' | 'status' | 'source'
type SortDir = 'asc' | 'desc'

const SOURCE_LABELS: Record<string, string> = {
  trending: 'Trending',
  audience_request: 'Audience Request',
  era_gap: 'Era Gap',
  manual: 'Manual',
}

function scoreTier(score: number): { label: string; cls: string } {
  if (score > 0.8) return { label: 'HOT', cls: 'text-error bg-error/20 border-error/30' }
  if (score >= 0.6) return { label: 'WARM', cls: 'text-warning bg-warning/20 border-warning/30' }
  return { label: 'COOL', cls: 'text-dim bg-bg-2 border-border' }
}

function sortItems(items: QueueItem[], key: SortKey, dir: SortDir): QueueItem[] {
  return [...items].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    const cmp = typeof av === 'number' ? av - (bv as number) : String(av).localeCompare(String(bv))
    return dir === 'asc' ? cmp : -cmp
  })
}

export function QueueView() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [newTopic, setNewTopic] = useState('')
  const [adding, setAdding] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const load = async () => {
    try {
      const data = await fetchQueue() as unknown as QueueItem[]
      setItems(data)
    } catch {
      showToast('Failed to load queue', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!newTopic.trim() || adding) return
    setAdding(true)
    try {
      await addToQueue(newTopic.trim())
      setNewTopic('')
      showToast('Topic added')
      await load()
    } catch {
      showToast('Failed to add topic', 'error')
    } finally {
      setAdding(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteFromQueue(id)
      setItems(items.filter(i => i.id !== id))
      showToast('Topic removed')
    } catch {
      showToast('Failed to remove topic', 'error')
    }
  }

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir(key === 'score' ? 'desc' : 'asc')
    }
  }

  const sorted = sortItems(items, sortKey, sortDir)
  const arrow = (key: SortKey) => sortKey === key ? (sortDir === 'asc' ? ' \u25B4' : ' \u25BE') : ''

  return (
    <div class="p-4">
      {/* Add form */}
      <div class="flex gap-2 mb-4">
        <input
          type="text"
          value={newTopic}
          onInput={(e) => setNewTopic((e.target as HTMLInputElement).value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
          placeholder="Add a topic..."
          class="flex-1 bg-bg-2 border border-border text-bright px-3 py-2 rounded text-sm font-mono outline-none focus:border-running"
        />
        <button
          onClick={handleAdd}
          disabled={adding || !newTopic.trim()}
          class="px-4 py-2 text-xs font-bold bg-running/20 text-running border border-running/30 rounded hover:bg-running/30 disabled:opacity-50"
        >
          ADD
        </button>
      </div>

      {/* Queue list */}
      {loading ? (
        <div class="text-dim text-sm">Loading...</div>
      ) : items.length === 0 ? (
        <EmptyState title="Queue is empty">
          <span>Add topics above to get started</span>
        </EmptyState>
      ) : (
        <div>
          {/* Column headers */}
          <div class="flex items-center gap-3 px-3 py-2 text-[10px] tracking-wider text-dim">
            <span class="w-16">STATUS</span>
            <button class="flex-1 text-left hover:text-text" onClick={() => handleSort('topic')}>
              TOPIC{arrow('topic')}
            </button>
            <span class="w-10 text-center">TIER</span>
            <button class="w-14 text-right hover:text-text" onClick={() => handleSort('score')}>
              SCORE{arrow('score')}
            </button>
            <button class="w-24 text-right hover:text-text" onClick={() => handleSort('source')}>
              SOURCE{arrow('source')}
            </button>
            <span class="w-5" />
          </div>

          <div class="space-y-1">
            {sorted.map(item => {
              const tier = scoreTier(item.score)
              const expanded = expandedId === item.id
              return (
                <div key={item.id}>
                  <div
                    class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-3 flex items-center gap-3 cursor-pointer"
                    onClick={() => setExpandedId(expanded ? null : item.id)}
                  >
                    <span class={`text-xs px-1.5 py-0.5 rounded w-16 text-center ${
                      item.status === 'queued' ? 'bg-running/20 text-running' :
                      item.status === 'done' ? 'bg-success/20 text-success' :
                      'bg-dim/20 text-dim'}`}>{item.status}</span>
                    <span class="text-sm text-bright flex-1">{item.topic}</span>
                    <span class={`text-[9px] px-1.5 py-0.5 rounded border font-bold w-10 text-center ${tier.cls}`}>
                      {tier.label}
                    </span>
                    <span class="text-xs text-dim w-14 text-right">{item.score.toFixed(2)}</span>
                    <span class="text-xs text-dim w-24 text-right">{SOURCE_LABELS[item.source] ?? item.source}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                      class="text-dim hover:text-error text-xs w-5 text-center"
                      aria-label={`Delete ${item.topic}`}
                    >
                      ×
                    </button>
                  </div>
                  {/* Expanded detail */}
                  {expanded && (
                    <div class="bg-bg-2 border border-border/50 rounded-b mx-1 px-3 py-2 text-[10px] space-y-1">
                      <div class="flex gap-2">
                        <span class="text-dim w-20">Score</span>
                        <span class="text-bright">{item.score.toFixed(4)}</span>
                      </div>
                      <div class="flex gap-2">
                        <span class="text-dim w-20">Source</span>
                        <span class="text-text">{SOURCE_LABELS[item.source] ?? item.source}</span>
                      </div>
                      {Object.entries(item)
                        .filter(([k]) => !['id', 'topic', 'status', 'score', 'source'].includes(k))
                        .map(([k, v]) => (
                          <div key={k} class="flex gap-2">
                            <span class="text-dim w-20">{k.replace(/_/g, ' ')}</span>
                            <span class="text-text">{typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}</span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <div class="text-dim text-[10px] mt-3">{items.length} topic{items.length !== 1 ? 's' : ''}</div>
        </div>
      )}
    </div>
  )
}
