/**
 * Tween a number from `from` to `to` over `duration` ms with cubic-out easing.
 * Calls `onFrame(current)` each animation frame. Returns a cancel function.
 */
export function tweenNumber(
  from: number,
  to: number,
  duration: number,
  onFrame: (value: number) => void,
): () => void {
  const start = performance.now()
  let raf: number

  function tick(now: number) {
    const elapsed = now - start
    const t = Math.min(elapsed / duration, 1)
    // Cubic-out easing: 1 - (1-t)^3
    const eased = 1 - Math.pow(1 - t, 3)
    const current = from + (to - from) * eased
    onFrame(current)
    if (t < 1) {
      raf = requestAnimationFrame(tick)
    }
  }

  raf = requestAnimationFrame(tick)
  return () => cancelAnimationFrame(raf)
}
