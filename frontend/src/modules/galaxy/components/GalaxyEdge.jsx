import { motion } from 'framer-motion'
import { buildEdgePath, getEdgeStroke } from '../utils/edgeVisuals'

const Motion = motion

export function GalaxyEdge({ edge, highlighted, bidirectional, reducedMotion = false }) {
  const path = buildEdgePath(edge.source, edge.target, bidirectional ? 'double' : 'single')
  const visual = getEdgeStroke(edge.weight, highlighted)

  return (
    <Motion.path
      d={path}
      fill="none"
      stroke={visual.stroke}
      strokeWidth={visual.strokeWidth}
      markerEnd="url(#galaxy-arrow)"
      className={highlighted ? 'edge-highlight' : ''}
      initial={{ pathLength: 0, opacity: 0 }}
      animate={reducedMotion ? { pathLength: 1, opacity: 0.9 } : { pathLength: 1, opacity: highlighted ? 0.94 : 0.66 }}
      transition={{ duration: reducedMotion ? 0.16 : 0.9 }}
    />
  )
}
