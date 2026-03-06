export function SuccessBanner({ message }) {
  if (!message) return null
  return <div className="panel success-banner">{message}</div>
}
