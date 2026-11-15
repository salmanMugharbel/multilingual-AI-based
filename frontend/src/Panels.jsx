import React, { useEffect, useRef, useState } from 'react'
import { api, streamNDJSON } from './api.js'
import { where } from './Message.jsx'

function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="overlay" onClick={onClose}>
      <div className={`modal ${wide ? 'wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3 dir="auto">{title}</h3>
          <button className="btn small ghost" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

// Shows the original document. PDFs are rendered page by page on the server,
// with the cited passage highlighted on the cited page.
export function Viewer({ source, onClose }) {
  const isPdf = source.ext === '.pdf'
  const [page, setPage] = useState(source.page || 1)
  const [pages, setPages] = useState(null)
  const [img, setImg] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isPdf) return
    let url, cancelled = false
    setLoading(true)
    fetch(`/api/documents/${source.doc_id}/page/${page}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ highlight: page === source.page ? source.text : null }),
    }).then(async (r) => {
      if (!r.ok) throw new Error(r.statusText)
      setPages(Number(r.headers.get('X-Page-Count')) || null)
      url = URL.createObjectURL(await r.blob())
      if (!cancelled) setImg(url)
    }).catch(() => setImg(null)).finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [page])

  return (
    <Modal wide title={`${source.filename}${isPdf ? ` — page ${page}${pages ? ` of ${pages}` : ''}` : source.section ? ' — ' + where(source) : ''}`} onClose={onClose}>
      {source.text && (
        <div className="quote" dir="auto"><b>Cited passage{source.page ? ` (page ${source.page})` : ''}:</b> {source.text}</div>
      )}
      {isPdf ? (
        <>
          <div className="pager">
            <button className="btn small" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Prev</button>
            <span className="muted small">{loading ? 'Rendering…' : page === source.page ? 'Cited passage highlighted in yellow' : ''}</span>
            <button className="btn small" disabled={pages && page >= pages} onClick={() => setPage(page + 1)}>Next ›</button>
            <a className="small" href={api.fileUrl(source.doc_id, page)} target="_blank" rel="noreferrer">Open original PDF ↗</a>
          </div>
          <div className="pageview">{img && <img src={img} alt={`page ${page}`} />}</div>
        </>
      ) : (
        <p className="muted">This file type has no fixed pages; the cited section is shown above.
          <a href={api.fileUrl(source.doc_id)} target="_blank" rel="noreferrer"> Download original</a></p>
      )}
    </Modal>
  )
}

const LANGS = [['', 'Document language'], ['en', 'English'], ['ar', 'العربية'], ['ru', 'Русский']]

export function SummaryPanel({ doc, onClose }) {
  const [lang, setLang] = useState('')
  const [text, setText] = useState('')
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const ctrl = useRef(null)

  const run = async (l) => {
    ctrl.current?.abort()
    const c = new AbortController()
    ctrl.current = c
    setText(''); setError(''); setProgress(null); setRunning(true)
    try {
      await streamNDJSON(`/api/documents/${doc.id}/summary`, { lang: l || null }, (ev) => {
        if (ev.type === 'progress') setProgress(ev)
        else if (ev.type === 'token') { setProgress(null); setText((t) => t + ev.text) }
        else if (ev.type === 'error') setError(ev.message)
      }, c.signal)
    } catch (e) { if (e.name !== 'AbortError') setError(e.message) }
    setRunning(false)
  }

  useEffect(() => { run(lang); return () => ctrl.current?.abort() }, [lang])

  return (
    <Modal title={`Summary — ${doc.filename}`} onClose={onClose}>
      <div className="summary-controls">
        <label>Language:
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            {LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        {running && <span className="muted"><span className="spinner" />
          {progress?.step === 'final' ? ' Combining part summaries…'
            : progress ? ` Summarising part ${progress.step} of ${progress.total}…` : ' Generating…'}
        </span>}
      </div>
      {error && <div className="error">{error}</div>}
      <div className="summary" dir="auto">{text}</div>
      <p className="muted small">Long documents are summarised with map-reduce: each part is summarised separately,
        then the part summaries are combined. Summaries are cached per language.</p>
    </Modal>
  )
}
