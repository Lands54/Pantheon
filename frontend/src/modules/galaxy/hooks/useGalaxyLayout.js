import { useMemo } from 'react'
import { buildGalaxyLayout } from '../utils/layout'

export function useGalaxyLayout(agentRows, viewport, selectedAgentId) {
  return useMemo(
    () => buildGalaxyLayout(agentRows, viewport, selectedAgentId),
    [agentRows, viewport, selectedAgentId],
  )
}
