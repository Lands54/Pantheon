export function TabStrip({ items = [], value, onChange }) {
  return (
    <div className="tab-strip">
      {items.map((item) => (
        <button
          key={item.id}
          className={`tab-chip ${value === item.id ? 'active' : ''}`}
          onClick={() => onChange?.(item.id)}
        >
          {item.icon ? <item.icon size={14} /> : null}
          {item.label}
        </button>
      ))}
    </div>
  )
}
