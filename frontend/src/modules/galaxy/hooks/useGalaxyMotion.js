import { useReducedMotion } from '../../../hooks/useReducedMotion'

export function useGalaxyMotion() {
  const reducedMotion = useReducedMotion()
  return {
    reducedMotion,
    presets: {
      nodeHover: reducedMotion ? {} : { scale: 1.05 },
      panelEnter: reducedMotion ? { opacity: 1 } : { opacity: [0, 1], y: [12, 0] },
      linkingRingRotate: reducedMotion ? {} : { rotate: 360 },
    },
  }
}
