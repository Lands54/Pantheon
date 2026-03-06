export function Chip({ className = '', children }) {
  return <span className={`chip ${className}`.trim()}>{children}</span>
}
