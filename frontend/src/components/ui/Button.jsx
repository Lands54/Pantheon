export function Button({ variant = 'primary', className = '', children, ...props }) {
  const tone = variant === 'ghost' ? 'ghost-btn' : 'primary-btn'
  return (
    <button className={`${tone} ${className}`.trim()} {...props}>
      {children}
    </button>
  )
}
