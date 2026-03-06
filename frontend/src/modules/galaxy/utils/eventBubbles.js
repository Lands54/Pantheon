import { clamp } from '../../../utils/numbers'
import { getBubbleColor } from './colors'

export function buildEventBubbles(queueCount, hasInbox) {
  const visible = clamp(Number(queueCount || 0), 0, 12)
  return Array.from({ length: visible }, (_, index) => {
    const orbit = index < 8 ? 1 : 2
    const total = orbit === 1 ? Math.min(visible, 8) : Math.max(1, visible - 8)
    const slot = orbit === 1 ? index : index - 8
    const radius = orbit === 1 ? 48 : 62
    const angle = (-Math.PI / 2) + (slot / total) * Math.PI * 2
    return {
      orbit,
      index,
      radius: orbit === 1 ? 5 : 4,
      angle,
      x: radius * Math.cos(angle),
      y: radius * Math.sin(angle),
      driftX: (index % 2 === 0 ? 1 : -1) * (3 + (index % 3)),
      driftY: (index % 2 === 0 ? -1 : 1) * (2 + ((index + 1) % 3)),
      duration: 2.8 + index * 0.18,
      delay: index * 0.05,
      color: getBubbleColor(index, hasInbox),
    }
  })
}
