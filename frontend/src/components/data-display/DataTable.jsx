export function DataTable({ children, className = '' }) {
  return <div className={`table-wrap ${className}`.trim()}>{children}</div>
}
