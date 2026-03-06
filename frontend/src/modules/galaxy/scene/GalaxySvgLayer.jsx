import { GalaxyEdge } from '../components/GalaxyEdge'
import { GalaxyNode } from '../components/GalaxyNode'
import { isBidirectional } from '../utils/edgeVisuals'

export function GalaxySvgLayer({
  viewport,
  connections,
  matrix,
  agentRows,
  positions,
  selectedAgentId,
  linkModeSource,
  reducedMotion,
  onSelectNode,
}) {
  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${viewport.width} ${viewport.height}`}>
      <defs>
        <marker id="galaxy-arrow" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(226,232,240,0.9)" />
        </marker>
      </defs>

      {connections.map((edge) => (
        <GalaxyEdge
          key={`${edge.sourceId}-${edge.targetId}`}
          edge={edge}
          highlighted={!!selectedAgentId && (edge.sourceId === selectedAgentId || edge.targetId === selectedAgentId)}
          bidirectional={isBidirectional(matrix, edge.sourceId, edge.targetId)}
          reducedMotion={reducedMotion}
        />
      ))}

      {agentRows.map((agent) => {
        const position = positions[agent.agent_id]
        if (!position) return null
        return (
          <GalaxyNode
            key={agent.agent_id}
            agent={agent}
            position={position}
            selected={selectedAgentId === agent.agent_id}
            linking={linkModeSource === agent.agent_id}
            reducedMotion={reducedMotion}
            onSelect={onSelectNode}
          />
        )
      })}
    </svg>
  )
}
