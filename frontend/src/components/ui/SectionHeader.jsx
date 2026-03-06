export function SectionHeader({ eyebrow, title, actions = null, children = null }) {
  return (
    <div className="section-header">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        {title ? <h3>{title}</h3> : null}
        {children}
      </div>
      {actions}
    </div>
  )
}
