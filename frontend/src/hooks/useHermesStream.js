import { useMemo, useEffect, useState } from 'react'

function edgeKey(source, target, kind) {
  return `${source}->${target}:${kind}`
}

export function useHermesStream(projectId) {
  const [connected, setConnected] = useState(false)
  const [degraded, setDegraded] = useState(false)
  const [recent, setRecent] = useState([])
  const [nodes, setNodes] = useState({})
  const [edges, setEdges] = useState({})

  useEffect(() => {
    if (!projectId) return undefined

    let es
    try {
      es = new EventSource(`/hermes/events?project_id=${encodeURIComponent(projectId)}`)
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
        const ev = JSON.parse(msg.data)
        setRecent((prev) => [ev, ...prev].slice(0, 30))

        setNodes((prev) => {
          const next = { ...prev }
          const payload = ev?.payload || {}
          const ensureNode = (id, label, kind) => {
            if (!next[id]) next[id] = { id, label, kind }
          }
          if (ev?.type === 'protocol_registered') {
            const protocolId = `protocol:${payload.name}@${payload.version || '1.0.0'}`
            const agentNode = `agent:${payload?.provider?.agent_id || 'unknown'}`
            ensureNode(protocolId, payload.name || 'unknown.protocol', 'protocol')
            ensureNode(agentNode, payload?.provider?.agent_id || 'unknown', 'agent')
          }
          if (ev?.type === 'protocol_invoked') {
            const protocolId = `protocol:${payload.name}@${payload.version || '1.0.0'}`
            const caller = `agent:${payload.caller_id || 'unknown'}`
            ensureNode(protocolId, payload.name || 'unknown.protocol', 'protocol')
            ensureNode(caller, payload.caller_id || 'unknown', 'agent')
          }
          return next
        })

        setEdges((prev) => {
          const next = { ...prev }
          const payload = ev?.payload || {}
          const bump = (source, target, kind) => {
            const key = edgeKey(source, target, kind)
            const cur = next[key] || { key, source, target, kind, count: 0 }
            next[key] = { ...cur, count: cur.count + 1 }
          }
          if (ev?.type === 'protocol_registered') {
            const protocolId = `protocol:${payload.name}@${payload.version || '1.0.0'}`
            const agentNode = `agent:${payload?.provider?.agent_id || 'unknown'}`
            bump(agentNode, protocolId, 'provides')
          }
          if (ev?.type === 'protocol_invoked') {
            const protocolId = `protocol:${payload.name}@${payload.version || '1.0.0'}`
            const caller = `agent:${payload.caller_id || 'unknown'}`
            bump(caller, protocolId, 'invokes')
          }
          return next
        })
      } catch {
        // ignore malformed stream message
      }
    }

    es.onerror = () => {
      setConnected(false)
      setDegraded(true)
    }

    return () => {
      es.close()
    }
  }, [projectId])

  return useMemo(() => ({ connected, degraded, recent, nodes, edges }), [connected, degraded, recent, nodes, edges])
}
