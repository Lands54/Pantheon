import { useEffect, useRef, useState } from 'react'
import { getAgentStatus } from '../api/platformApi'
import { usePolling } from '../hooks/usePolling'
import { useHermesStream } from '../hooks/useHermesStream'
import { useAgentStatusStream } from '../hooks/useAgentStatusStream'
import { AgentStatusTable } from '../components/AgentStatusTable'

export function DashboardPage({ projectId, onPickAgent }) {
  const [error, setError] = useState('')
  const reqSeqRef = useRef(0)
  const hermes = useHermesStream(projectId)
  const statusStream = useAgentStatusStream(projectId)

  const loadStatus = async (pid = projectId) => {
    if (!pid) return
    const reqSeq = ++reqSeqRef.current
    try {
      const data = await getAgentStatus(pid)
      if (reqSeq !== reqSeqRef.current || pid !== projectId) return
      statusStream.setAgents(data.agents || [])
      setError('')
    } catch (err) {
      if (reqSeq !== reqSeqRef.current || pid !== projectId) return
      setError(String(err.message || err))
    }
  }

  useEffect(() => {
    statusStream.setAgents([])
    setError('')
    loadStatus(projectId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  usePolling(async () => {
    if (!statusStream.connected) await loadStatus()
  }, 10000, [projectId, statusStream.connected])

  const nodes = Object.keys(hermes.nodes || {}).length
  const edges = Object.keys(hermes.edges || {}).length

  return (
    <div className="stack-lg">
      <div className="grid-3">
        <div className="panel metric">
          <div className="label">Current Project</div>
          <div className="value">{projectId}</div>
        </div>
        <div className="panel metric">
          <div className="label">Hermes Stream</div>
          <div className="value">{hermes.connected ? 'Connected' : 'Disconnected'}</div>
          {hermes.degraded && <div className="warn">Realtime degraded, polling fallback active</div>}
        </div>
        <div className="panel metric">
          <div className="label">Agent Status Stream</div>
          <div className="value">{statusStream.connected ? 'Connected' : 'Disconnected'}</div>
          {statusStream.degraded && <div className="warn">Agent status uses polling fallback</div>}
        </div>
      </div>

      <div className="panel metric">
        <div className="label">Hermes Topology</div>
        <div className="value">{nodes} nodes / {edges} edges</div>
      </div>

      {error && <div className="panel error-banner">{error}</div>}

      <AgentStatusTable rows={statusStream.agents} onPickAgent={onPickAgent} />

      <div className="panel">
        <h3>Hermes Event Feed (SSE)</h3>
        <div className="log-list">
          {(hermes.recent || []).slice(0, 20).map((ev, idx) => (
            <div className="log-row" key={`${ev.seq || idx}-${idx}`}>
              <span className="mono">{ev.type || 'event'}</span>
              <span className="mono dim">{JSON.stringify(ev.payload || {}).slice(0, 160)}</span>
            </div>
          ))}
          {!hermes.recent?.length && <div className="dim">No live Hermes events yet</div>}
        </div>
      </div>
    </div>
  )
}
