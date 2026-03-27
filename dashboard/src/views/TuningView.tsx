import { useEffect } from 'preact/hooks'
import { tuningData, tuningLoading, tuningError, fetchTuningData } from '../state/tuning'
import { Skeleton } from '../components/Skeleton'
import { MaturityOverview } from '../components/tuning/MaturityOverview'
import { TopicHealth } from '../components/tuning/TopicHealth'
import { ParameterOverrides } from '../components/tuning/ParameterOverrides'
import { Recommendations } from '../components/tuning/Recommendations'
import { OverrideHistory } from '../components/tuning/OverrideHistory'

export function TuningView() {
  useEffect(() => {
    if (!tuningData.value) {
      fetchTuningData()
    }
  }, [])

  if (tuningLoading.value && !tuningData.value) {
    return (
      <div class="p-4 space-y-4">
        <Skeleton height="10rem" />
        <Skeleton height="6rem" />
        <Skeleton height="20rem" />
      </div>
    )
  }

  if (tuningError.value && !tuningData.value) {
    return (
      <div class="p-4">
        <div class="backdrop-blur-sm bg-bg-1/80 border border-error/30 rounded p-4">
          <div class="text-error text-sm">{tuningError.value}</div>
        </div>
      </div>
    )
  }

  const data = tuningData.value
  const correlation = data?.correlation ?? {}
  const layers = correlation.layers ?? {}
  const recommendations = correlation.recommendations ?? []
  const history = data?.history ?? []

  return (
    <div class="p-4 space-y-4">
      {/* Row 1: Maturity + Topic Health */}
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MaturityOverview correlation={correlation} />
        <TopicHealth layer={layers['3']} />
      </div>

      {/* Row 2: Parameter Overrides */}
      <ParameterOverrides />

      {/* Row 3: Recommendations */}
      <Recommendations recommendations={recommendations} />

      {/* Row 4: Override History */}
      <OverrideHistory history={history} />
    </div>
  )
}
