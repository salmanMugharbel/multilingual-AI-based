import React, { useRef, useState } from 'react'
import { api } from './api.js'

const LANG_LABEL = { en: 'EN', ar: 'AR', ru: 'RU' }

export function Sidebar({ docs, selected, setSelected, onChange, onSummary, onOpen }) {
  const [uploading, setUploading] = useState([])
  const [error, setError] = useState('')
  const [drag, setDrag] = useState(false)
  const inputRef = useRef(null)

  const upload = async (files) => {
    setError('')
    for (const f of files) {
      setUploading((u) => [...u, f.name])
      try { await api.upload(f) } catch (e) { setError(`${f.name}: ${e.message}`) }
      setUploading((u) => u.filter((n) => n !== f.name))
      onChange()
    }
  }

  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])

  const remove = async (d) => {
    if (!confirm(`Delete "${d.filename}"?`)) return
    await api.remove(d.id)
    setSelected((s) => s.filter((x) => x !== d.id))
    onChange()
  }

  return (
    <aside className="sidebar">
      <div className={`drop ${drag ? 'drag' : ''}`}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload([...e.dataTransfer.files]) }}>
        <div className="drop-icon">⇪</div>
        <b>Upload documents</b>
        <span>PDF · DOCX · TXT — drag & drop or click</span>
        <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.txt,.md" hidden
          onChange={(e) => { upload([...e.target.files]); e.target.value = '' }} />
      </div>
      {uploading.map((n) => <div key={n} className="uploading"><span className="spinner" /> Processing {n}…</div>)}
      {error && <div className="error">{error}</div>}

      <div className="doclist-head">
        <h3>Documents ({docs.length})</h3>
        {selected.length > 0 && <button className="link" onClick={() => setSelected([])}>clear selection</button>}
      </div>
      <p className="muted small">Tick documents to limit the search to them.</p>
      <ul className="doclist">
        {docs.map((d) => (
          <li key={d.id} className={selected.includes(d.id) ? 'sel' : ''}>
            <label className="docmain">
              <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
              <div>
                <div className="docname" dir="auto" title={d.filename}>{d.filename}</div>
                <div className="docmeta">
                  <span className="badge">{LANG_LABEL[d.language] || d.language}</span>
                  {d.pages ? `${d.pages} pages` : `${d.sections} sections`} · {d.chunks} chunks · {d.words.toLocaleString()} words
                </div>
              </div>
            </label>
            <div className="docactions">
              <button className="btn small" onClick={() => onSummary(d)}>Summary</button>
              <button className="btn small ghost" onClick={() => onOpen(d)}>Open</button>
              <button className="btn small ghost danger" onClick={() => remove(d)} title="Delete">✕</button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  )
}
