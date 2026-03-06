export function buildGalaxyLayout(rows, size, selectedAgentId) {
  const list = Array.isArray(rows) ? rows : []
  const width = Math.max(640, Number(size?.width || 0))
  const height = Math.max(480, Number(size?.height || 0))
  const center = { x: width / 2, y: height / 2, orbit: 0, slot: 0 }
  if (!list.length) return {}

  const selected = list.find((item) => item.agent_id === selectedAgentId) || null
  const ordered = selected
    ? [selected, ...list.filter((item) => item.agent_id !== selectedAgentId)]
    : [...list].sort((a, b) => {
        const aWeight = (a.active ? 2 : 0) + (String(a.worker_state || '').toLowerCase() === 'running' ? 1 : 0)
        const bWeight = (b.active ? 2 : 0) + (String(b.worker_state || '').toLowerCase() === 'running' ? 1 : 0)
        return bWeight - aWeight || String(a.agent_id).localeCompare(String(b.agent_id))
      })

  const positions = {}
  positions[ordered[0].agent_id] = center

  const others = ordered.slice(1)
  if (!others.length) return positions

  const maxRing = Math.max(1, Math.ceil(others.length / 6))
  const maxRadius = Math.max(140, Math.min(width, height) / 2 - 70)
  const radiusStep = maxRadius / (maxRing + 0.35)
  let cursor = 0

  for (let ring = 1; cursor < others.length; ring += 1) {
    const capacity = ring * 6
    const radius = Math.min(maxRadius, 70 + ring * radiusStep)
    for (let slot = 0; slot < capacity && cursor < others.length; slot += 1) {
      const angle = (-Math.PI / 2) + (slot / capacity) * Math.PI * 2 + (ring % 2 === 0 ? 0.18 : -0.08)
      const item = others[cursor]
      positions[item.agent_id] = {
        x: center.x + radius * Math.cos(angle),
        y: center.y + radius * Math.sin(angle),
        orbit: ring,
        slot,
      }
      cursor += 1
    }
  }

  return positions
}
