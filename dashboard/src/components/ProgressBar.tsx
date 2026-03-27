import { stageNum, isRunning } from '../state/store'

export function ProgressBar() {
  if (!isRunning.value) return null

  const pct = (stageNum.value / 13) * 100

  return (
    <div
      class="fixed bottom-0 left-0 w-full h-[3px] z-50"
      style={{ background: 'transparent' }}
    >
      <div
        class="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500"
        style={{
          width: `${pct}%`,
          boxShadow: '0 0 8px rgba(6, 182, 212, 0.6)',
        }}
      />
    </div>
  )
}
