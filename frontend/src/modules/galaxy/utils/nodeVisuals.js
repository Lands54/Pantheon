import { getStatusColor } from './colors'

export function getNodeCoreColor(agent) {
  const workerState = String(agent?.worker_state || 'idle').toLowerCase()
  if (workerState === 'running') return 'var(--accent-orange)'
  if (agent?.active) return 'var(--accent-cyan)'
  return '#cbd5e1'
}

export function getNodeShellColor(agent) {
  return agent?.active ? 'rgba(255,255,255,0.14)' : 'rgba(148,163,184,0.18)'
}

export function getNodeStatusColor(agent) {
  return getStatusColor(agent?.worker_state)
}

export function getNodeRingMode(agent, selected, linking) {
  if (linking) return 'linking'
  if (selected) return 'selected'
  if (agent?.has_pending_inbox) return 'inbox'
  return 'idle'
}

export function getQueueVisualLevel(agent) {
  const queued = Number(agent?.queued_pulse_events || 0)
  if (queued >= 12) return 'overflow'
  if (queued >= 8) return 'dense'
  if (queued > 0) return 'normal'
  return 'none'
}
