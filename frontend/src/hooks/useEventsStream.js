import { useEffect, useState } from 'react'

function buildQuery(projectId, filters = {}) {
  const params = new URLSearchParams()
  params.set('project_id', projectId)
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && `${v}` !== '') params.set(k, `${v}`)
  })
  return params.toString()
}

export function useEventsStream(projectId, filters) {
  const [items, setItems] = useState([])
  const [connected, setConnected] = useState(false)
  const [degraded, setDegraded] = useState(false)

  const filterKey = JSON.stringify(filters || {})

  useEffect(() => {
    if (!projectId) return undefined

    const q = buildQuery(projectId, filters || {})
    let es
    try {
      es = new EventSource(`/events/stream?${q}`)
    } catch {
      setTimeout(() => {
        setConnected(false)
        setDegraded(true)
      }, 0)
      return undefined
    }

    es.onopen = () => {
      setConnected(true)
      setDegraded(false)
    }

    es.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        if (Array.isArray(data.items)) setItems(data.items)
      } catch {
        // ignore malformed stream payload
      }
    }

    es.onerror = () => {
      setConnected(false)
      setDegraded(true)
    }

    return () => es.close()
  }, [projectId, filterKey, filters])

  return { items, connected, degraded, setItems }
}
