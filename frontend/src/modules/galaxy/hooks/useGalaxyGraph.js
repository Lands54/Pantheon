import { useEffect, useState } from 'react'
import { usePolling } from '../../../hooks/usePolling'
import { loadGalaxyViewModel } from '../../../store/galaxy/galaxyViewModel'

export function useGalaxyGraph(projectId, agentRows) {
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [workspaceError, setWorkspaceError] = useState('')
  const [workspace, setWorkspace] = useState({
    graph: { nodes: [], matrix: {} },
    recentEvents: [],
    timelineSummary: [],
    mailbox: { inbox: [], outbox: [] },
    infrastructure: { contracts: [], ports: { leases: [] } },
    council: null,
    metrics: { total: 0, running: 0, active: 0, inbox: 0, queued: 0, edges: 0 },
  })

  const refreshWorkspace = async (options = {}) => {
    const { silent = false } = options
    if (!silent) setWorkspaceLoading(true)
    try {
      const next = await loadGalaxyViewModel(projectId, agentRows)
      setWorkspace(next)
      if (!next.errors?.length) setWorkspaceError('')
      else if (!silent) setWorkspaceError(String(next.errors[0]?.message || next.errors[0] || 'workspace load failed'))
      return next
    } catch (err) {
      if (!silent) setWorkspaceError(String(err?.message || err))
      throw err
    } finally {
      if (!silent) setWorkspaceLoading(false)
    }
  }

  useEffect(() => {
    refreshWorkspace().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  usePolling(() => {
    refreshWorkspace({ silent: true }).catch(() => {})
  }, 12000, [projectId, JSON.stringify((agentRows || []).map((item) => item.agent_id))])

  return {
    workspace,
    workspaceLoading,
    workspaceError,
    refreshWorkspace,
  }
}
