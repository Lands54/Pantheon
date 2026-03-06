export function selectProjectStats(agentRows = []) {
  const rows = Array.isArray(agentRows) ? agentRows : []
  return {
    total: rows.length,
    active: rows.filter((item) => item.active).length,
    running: rows.filter((item) => String(item.worker_state || '').toLowerCase() === 'running').length,
    pendingInbox: rows.filter((item) => item.has_pending_inbox).length,
    queued: rows.reduce((sum, item) => sum + Number(item.queued_pulse_events || 0), 0),
  }
}

export function selectSelectedAgent(agentRows = [], selectedAgentId = '') {
  return (Array.isArray(agentRows) ? agentRows : []).find((item) => item.agent_id === selectedAgentId) || null
}

export function selectAgentSettingsMap(config = {}, projectId = '') {
  const project = (config?.projects || {})[projectId] || {}
  return project?.agent_settings && typeof project.agent_settings === 'object'
    ? project.agent_settings
    : {}
}

export function selectGalaxyMetrics(agentRows = [], matrix = {}) {
  const stats = selectProjectStats(agentRows)
  const edges = Object.values(matrix || {}).reduce(
    (sum, row) => sum + Object.values(row || {}).filter((weight) => Number(weight || 0) > 0).length,
    0,
  )
  return {
    ...stats,
    edges,
  }
}
