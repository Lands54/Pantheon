export function StatusPill({ online = false, compact = false, children }) {
  return (
    <span className={`project-state-chip ${online ? 'online' : 'offline'} ${compact ? 'compact' : ''}`.trim()}>
      <span className="state-dot" />
      {children}
    </span>
  )
}
