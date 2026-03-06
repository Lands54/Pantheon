import { useEffect, useRef } from 'react'
import { GalaxyEmptyState } from '../components/GalaxyEmptyState'
import { GalaxyLegend } from '../components/GalaxyLegend'
import { GalaxyBackdrop } from './GalaxyBackdrop'
import { GalaxySvgLayer } from './GalaxySvgLayer'
import { useElementSize } from '../../../hooks/useElementSize'

export function GalaxyScene(props) {
  const containerRef = useRef(null)
  const viewport = useElementSize(containerRef)
  const {
    graphNodes = [],
    agentRows = [],
    onViewportChange,
  } = props

  useEffect(() => {
    onViewportChange?.(viewport)
  }, [onViewportChange, viewport])

  return (
    <div className="galaxy-stage" ref={containerRef}>
      <GalaxyBackdrop />
      <GalaxySvgLayer {...props} viewport={viewport} />
      {!graphNodes.length && !agentRows.length && <GalaxyEmptyState />}
      <GalaxyLegend />
    </div>
  )
}
