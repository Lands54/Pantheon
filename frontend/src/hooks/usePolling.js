import { useEffect } from 'react'

export function usePolling(fn, intervalMs, deps = []) {
  useEffect(() => {
    let alive = true
    const run = async () => {
      if (!alive) return
      try {
        await fn()
      } catch {
        // ignore polling errors; UI handles stale state.
      }
    }
    run()
    const id = setInterval(run, intervalMs)
    return () => {
      alive = false
      clearInterval(id)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
