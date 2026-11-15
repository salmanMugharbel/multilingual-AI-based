// Small API client for the FastAPI backend.

export async function getJSON(url, opts) {
  const r = await fetch(url, opts)
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  return r.json()
}

export const api = {
  health: () => getJSON('/api/health'),
  documents: () => getJSON('/api/documents'),
  remove: (id) => getJSON(`/api/documents/${id}`, { method: 'DELETE' }),
  upload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return getJSON('/api/documents', { method: 'POST', body: fd })
  },
  fileUrl: (id, page) => `/api/documents/${id}/file${page ? `#page=${page}` : ''}`,
}

// Read an NDJSON stream line by line and call onEvent for each JSON object.
export async function streamNDJSON(url, body, onEvent, signal) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (line) onEvent(JSON.parse(line))
    }
  }
  if (buf.trim()) onEvent(JSON.parse(buf))
}
