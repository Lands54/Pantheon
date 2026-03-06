import { motion } from 'framer-motion'

const Motion = motion

export function EventBubble({ bubble, hasInbox, pendingCount, reducedMotion = false }) {
  return (
    <Motion.g
      initial={{ scale: 0.5, opacity: 0 }}
      animate={reducedMotion ? { opacity: 0.78 } : {
        x: [bubble.x, bubble.x + bubble.driftX, bubble.x],
        y: [bubble.y, bubble.y + bubble.driftY, bubble.y],
        scale: [0.9, 1.12, 0.96],
        opacity: [0.62, 0.98, 0.72],
      }}
      transition={reducedMotion ? { duration: 0.2 } : {
        duration: bubble.duration,
        repeat: Infinity,
        ease: 'easeInOut',
        delay: bubble.delay,
      }}
    >
      <circle r={bubble.radius + 3} className="event-bubble-halo" fill={bubble.color} opacity={0.18} />
      <circle
        r={bubble.radius}
        className="event-bubble-core"
        fill={bubble.color}
        stroke={hasInbox ? 'rgba(255,245,157,0.82)' : 'rgba(255,255,255,0.78)'}
        strokeWidth="1.2"
      />
      {pendingCount > 12 && bubble.index === 0 && (
        <text textAnchor="middle" dy="3" className="event-bubble-text">+{pendingCount - 12}</text>
      )}
    </Motion.g>
  )
}
