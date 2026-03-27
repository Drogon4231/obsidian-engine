import type { CorrelationLayer, TopicRankingEntry } from '../../types'

interface Props {
  layer: CorrelationLayer | undefined
}

export function TopicHealth({ layer }: Props) {
  const status = layer?.status ?? 'inactive'
  const ranking = (layer?.results?.topic_ranking ?? []) as TopicRankingEntry[]

  return (
    <div class="backdrop-blur-sm bg-bg-1/80 border border-border rounded p-4">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-dim text-[10px] tracking-wider">TOPIC HEALTH (LAYER 3)</span>
        <span class={`text-[9px] px-1.5 py-0.5 rounded ${
          status === 'active' ? 'bg-success/20 text-success' :
          status === 'insufficient_data' ? 'bg-warning/20 text-warning' :
          'bg-bg-2 text-dim'
        }`}>
          {status.toUpperCase().replace('_', ' ')}
        </span>
      </div>

      {ranking.length === 0 ? (
        <div class="text-dim text-xs py-4 text-center">
          Need 2+ videos per topic for health analysis
        </div>
      ) : (
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-dim border-b border-border">
                <th class="text-left p-1.5">Topic</th>
                <th class="text-right p-1.5">Videos</th>
                <th class="text-right p-1.5">Shorts</th>
                <th class="text-right p-1.5">Avg Views</th>
                <th class="text-right p-1.5">Avg Retention</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((t, i) => (
                <tr key={i} class="border-b border-border/30">
                  <td class="p-1.5 text-bright font-medium">{t.topic}</td>
                  <td class="p-1.5 text-right text-text">{t.long_count}</td>
                  <td class="p-1.5 text-right text-text">{t.short_count}</td>
                  <td class="p-1.5 text-right text-text">
                    {t.avg_long_views != null ? t.avg_long_views.toLocaleString() : '-'}
                  </td>
                  <td class="p-1.5 text-right">
                    {t.avg_long_retention != null ? (
                      <span class={
                        t.avg_long_retention >= 50 ? 'text-success' :
                        t.avg_long_retention >= 35 ? 'text-warning' : 'text-error'
                      }>
                        {t.avg_long_retention.toFixed(1)}%
                      </span>
                    ) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
