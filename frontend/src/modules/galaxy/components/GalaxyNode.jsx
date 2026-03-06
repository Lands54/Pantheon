import { motion } from 'framer-motion'
import { buildEventBubbles } from '../utils/eventBubbles'
import {
  getNodeCoreColor,
  getNodeRingMode,
  getNodeShellColor,
  getNodeStatusColor,
} from '../utils/nodeVisuals'
import { EventBubble } from './EventBubble'
import { OrbitRing } from './OrbitRing'

const Motion = motion

export function GalaxyNode({ agent, position, selected, linking, reducedMotion, onSelect }) {
  const workerState = String(agent.worker_state || 'idle').toLowerCase()
  const isRunning = workerState === 'running'
  const statusColor = getNodeStatusColor(agent)
  const ringMode = getNodeRingMode(agent, selected, linking)
  const bubbles = buildEventBubbles(agent.queued_pulse_events, agent.has_pending_inbox)

  return (
    <Motion.g
      className="galaxy-node"
      transform={`translate(${position.x}, ${position.y})`}
      onClick={() => onSelect(agent.agent_id)}
      whileHover={reducedMotion ? undefined : { scale: 1.05 }}
      transition={{ type: 'spring', stiffness: 220, damping: 18 }}
    >
      <title>
        {`${agent.agent_id}
state=${agent.worker_state || 'idle'}
active=${agent.active ? 'yes' : 'no'}
queue=${agent.queued_pulse_events || 0}
inbox=${agent.has_pending_inbox ? 'pending' : 'empty'}`}
      </title>

      {isRunning && (
        <>
          <Motion.circle
            r={44}
            fill="none"
            stroke={statusColor}
            strokeWidth="1.5"
            initial={{ scale: 0.8, opacity: 0.42 }}
            animate={reducedMotion ? { opacity: 0.25 } : { scale: 1.35, opacity: 0 }}
            transition={reducedMotion ? { duration: 0.2 } : { duration: 2.4, repeat: Infinity, ease: 'easeOut' }}
          />
          <Motion.circle
            r={38}
            fill="none"
            stroke={statusColor}
            strokeWidth="1"
            initial={{ scale: 0.84, opacity: 0.24 }}
            animate={reducedMotion ? { opacity: 0.18 } : { scale: 1.22, opacity: 0 }}
            transition={reducedMotion ? { duration: 0.2 } : { duration: 2.4, repeat: Infinity, ease: 'easeOut', delay: 0.65 }}
          />
        </>
      )}

      {!!bubbles.length && <OrbitRing radius={50} />}
      {!!bubbles.length && bubbles.map((bubble) => (
        <EventBubble
          key={`${agent.agent_id}-bubble-${bubble.index}`}
          bubble={bubble}
          hasInbox={!!agent.has_pending_inbox}
          pendingCount={Number(agent.queued_pulse_events || 0)}
          reducedMotion={reducedMotion}
        />
      ))}

      {(selected || linking) && (
        <Motion.circle
          r={linking ? 52 : 46}
          className={`node-ring ${ringMode === 'linking' ? 'linking' : 'selected'}`}
          animate={reducedMotion ? { opacity: 0.9 } : (linking ? { rotate: 360 } : { opacity: [0.65, 1, 0.72] })}
          transition={reducedMotion ? { duration: 0.2 } : (linking ? { duration: 6, repeat: Infinity, ease: 'linear' } : { duration: 2.4, repeat: Infinity })}
        />
      )}

      {agent.has_pending_inbox && <circle r={38} className="node-inbox-ring" />}
      <circle r={34} className="node-shell" fill={getNodeShellColor(agent)} stroke={`rgba(255,255,255,${selected ? 0.52 : 0.24})`} strokeWidth="1.2" />
      <circle r={26} fill={getNodeCoreColor(agent)} stroke="rgba(255,255,255,0.84)" strokeWidth="2.4" className="node-core" />
      <text textAnchor="middle" dy="-2" className="node-label">{agent.agent_id.slice(0, 2).toUpperCase()}</text>
      <circle cx={25} cy={-24} r={7} fill={statusColor} stroke="rgba(255,255,255,0.9)" strokeWidth="2" className="node-status-dot" />

      {!!agent.queued_pulse_events && (
        <g transform="translate(29 27)">
          <circle r="10" className="node-queue-badge" />
          <text textAnchor="middle" dy="4" className="node-queue-text">{Math.min(Number(agent.queued_pulse_events || 0), 99)}</text>
        </g>
      )}

      <text textAnchor="middle" dy="52" className="node-caption">{agent.agent_id}</text>
      <text textAnchor="middle" dy="68" className="node-meta">{agent.worker_state || 'idle'} / q {agent.queued_pulse_events || 0}</text>
    </Motion.g>
  )
}
