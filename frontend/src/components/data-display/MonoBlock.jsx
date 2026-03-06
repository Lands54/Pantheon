export function MonoBlock({ children, className = '' }) {
  return <pre className={`mono ${className}`.trim()}>{children}</pre>
}
