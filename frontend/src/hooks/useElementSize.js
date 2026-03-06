import { useEffect, useState } from 'react'

export function useElementSize(ref, fallback = { width: 960, height: 620 }) {
  const [size, setSize] = useState(fallback)

  useEffect(() => {
    if (!ref.current) return undefined
    const element = ref.current
    const sync = () => {
      setSize({
        width: element.clientWidth || fallback.width,
        height: element.clientHeight || fallback.height,
      })
    }
    sync()
    const observer = new ResizeObserver(sync)
    observer.observe(element)
    return () => observer.disconnect()
  }, [fallback.height, fallback.width, ref])

  return size
}
