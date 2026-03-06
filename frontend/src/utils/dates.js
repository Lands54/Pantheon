export function toLocaleDateTime(ts) {
  if (!ts) return ''
  return new Date(Number(ts || 0) * 1000).toLocaleString()
}
