export function formatTimestamp(ts, fallback = '暂无') {
  if (!ts) return fallback
  return new Date(Number(ts || 0) * 1000).toLocaleString()
}
