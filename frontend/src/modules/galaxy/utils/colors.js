export function getStatusColor(workerState) {
  const state = String(workerState || 'idle').toLowerCase()
  if (state === 'running') return 'var(--accent-green)'
  if (state === 'failed' || state === 'dead') return 'var(--accent-danger)'
  if (state === 'cooldown' || state === 'queued') return 'var(--accent-cyan)'
  return 'var(--accent-amber)'
}

export function getBubbleColor(index, hasInbox) {
  const palette = hasInbox
    ? ['var(--accent-amber)', 'var(--accent-orange)', '#fb7185', 'var(--accent-cyan)']
    : ['var(--accent-cyan)', '#34d399', 'var(--accent-orange)', 'var(--accent-violet)']
  return palette[index % palette.length]
}
