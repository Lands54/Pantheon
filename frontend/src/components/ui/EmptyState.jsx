export function EmptyState({ className = '', children }) {
  return <div className={`dim ${className}`.trim()}>{children}</div>
}
