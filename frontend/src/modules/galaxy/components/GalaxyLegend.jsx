export function GalaxyLegend() {
  return (
    <div className="galaxy-legend">
      <div className="legend-item"><span className="quick-state running" /> running</div>
      <div className="legend-item"><span className="quick-state queued" /> queued</div>
      <div className="legend-item"><span className="quick-state idle" /> idle</div>
      <div className="legend-item"><span className="quick-state error" /> failed</div>
    </div>
  )
}
