import { useEffect, useState } from 'react'

export function useAgentStatusStream(projectId) {
  const [agents, setAgents] = useState([])
  const [connected, setConnected] = useState(false)
  const [degraded, setDegraded] = useState(false)

  useEffect(() => {
    if (!projectId) return undefined
    setAgents([])
    setConnected(false)

    let es
    try {
      es = new EventSource(`/agents/status/stream?project_id=${encodeURIComponent(projectId)}`)
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
        if (Array.isArray(data.agents)) setAgents(data.agents)
      } catch {
        // ignore malformed stream payload
      }
    }

    es.onerror = () => {
      setConnected(false)
      setDegraded(true)
    }

    return () => es.close()
  }, [projectId])

  return { agents, connected, degraded, setAgents }
}
