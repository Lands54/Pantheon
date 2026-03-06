export function isBidirectional(matrix = {}, sourceId, targetId) {
  return Number(matrix?.[targetId]?.[sourceId] || 0) > 0
}

export function buildEdgePath(source, target, mode = 'single') {
  if (!source || !target) return ''
  if (mode !== 'double') {
    return `M ${source.x} ${source.y} Q ${(source.x + target.x) / 2} ${(source.y + target.y) / 2} ${target.x} ${target.y}`
  }

  const dx = target.x - source.x
  const dy = target.y - source.y
  const distance = Math.sqrt(dx * dx + dy * dy) || 1
  const normalX = -dy / distance
  const normalY = dx / distance
  const offset = 24
  const cx = (source.x + target.x) / 2 + normalX * offset
  const cy = (source.y + target.y) / 2 + normalY * offset
  return `M ${source.x} ${source.y} Q ${cx} ${cy} ${target.x} ${target.y}`
}

export function getEdgeStroke(weight, highlighted) {
  return {
    stroke: highlighted ? 'rgba(250,204,21,0.92)' : 'rgba(226,232,240,0.38)',
    strokeWidth: Math.min(4, Math.max(1.2, Number(weight || 1))),
  }
}
