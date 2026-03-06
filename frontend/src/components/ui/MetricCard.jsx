export function MetricCard({ icon: Icon, label, value, className = '' }) {
  return (
    <div className={`summary-tile ${className}`.trim()}>
      {Icon ? <Icon size={16} /> : null}
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  )
}
