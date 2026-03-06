export function ErrorBanner({ message }) {
  if (!message) return null
  return <div className="panel error-banner">{message}</div>
}
