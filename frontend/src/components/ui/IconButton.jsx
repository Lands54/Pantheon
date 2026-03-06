export function IconButton({ className = '', children, ...props }) {
  return (
    <button className={`icon-btn ${className}`.trim()} {...props}>
      {children}
    </button>
  )
}
