import React, { useState } from 'react'

// Turn "text [1] more [2][3]" into text with clickable citation chips.
function withCitations(text, sources, onSource) {
  const parts = text.split(/(\[\d+\])/g)
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/)
    if (!m) return <React.Fragment key={i}>{p}</React.Fragment>
    const s = sources.find((x) => x.n === Number(m[1]))
    if (!s) return <React.Fragment key={i}>{p}</React.Fragment>
    return (
      <button key={i} className="cite" onClick={() => onSource(s)} title={`${s.filename} — ${where(s)}`}>
        {m[1]}
      </button>
    )
  })
}

export const where = (s) => (s.page ? `page ${s.page}` : s.section || '')

export function Message({ m, onSource }) {
  const [open, setOpen] = useState(false)
  if (m.role === 'user') return <div className="msg user"><div className="bubble" dir="auto">{m.text}</div></div>

  return (
    <div className="msg assistant">
      <div className="bubble">
        {m.pending && !m.text && (
          <div className="thinking"><span className="spinner" />
            {m.sources?.length ? `Found ${m.sources.length} relevant passages — generating answer…` : 'Searching documents…'}
          </div>
        )}
        <div className="answer" dir="auto">{withCitations(m.text, m.sources || [], onSource)}{m.pending && m.text && <span className="caret" />}</div>
        {m.error && <div className="error">{m.error}</div>}

        {m.sources?.length > 0 && (
          <div className="sources">
            <button className="link" onClick={() => setOpen(!open)}>
              {open ? '▾' : '▸'} Sources ({m.sources.length})
              {m.retrieval_ms != null && <span className="muted"> · search {m.retrieval_ms} ms{m.total_ms ? ` · total ${(m.total_ms / 1000).toFixed(1)} s` : ''}</span>}
            </button>
            <div className="chips">
              {m.sources.map((s) => (
                <button key={s.n} className="chip" onClick={() => onSource(s)}>
                  <b>[{s.n}]</b> {s.filename} · {where(s)}
                </button>
              ))}
            </div>
            {open && m.sources.map((s) => (
              <div key={s.n} className="source">
                <div className="source-head">
                  <b>[{s.n}] {s.filename}</b> — {where(s)}
                  <span className="score" title="cosine similarity between question and passage">relevance {s.score.toFixed(3)}</span>
                </div>
                <p dir="auto">{s.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
