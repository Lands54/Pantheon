const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function parseResponse(res) {
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : {}
  } catch {
    data = { detail: text || `HTTP ${res.status}` }
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`
    throw new Error(String(msg))
  }
  return data
}

export async function apiGet(path) {
  const res = await fetch(path)
  return parseResponse(res)
}

export async function apiPost(path, body = {}) {
  const res = await fetch(path, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  })
  return parseResponse(res)
}

export async function apiPut(path, body = {}) {
  const res = await fetch(path, {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  })
  return parseResponse(res)
}

export async function apiDelete(path) {
  const res = await fetch(path, { method: 'DELETE' })
  return parseResponse(res)
}
