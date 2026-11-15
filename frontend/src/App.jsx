import React, { useEffect, useRef, useState } from 'react'
import { api, streamNDJSON } from './api.js'
import { Sidebar } from './Sidebar.jsx'
import { Message } from './Message.jsx'
import { Viewer, SummaryPanel } from './Panels.jsx'

const LANGS = [
  { v: '', label: 'Auto (same as question)' },
  { v: 'en', label: 'English' },
  { v: 'ar', label: 'العربية' },
  { v: 'ru', label: 'Русский' },
]

const EXAMPLES = [
  'What is this document about?',
  'ما هي النقاط الرئيسية في هذا المستند؟',
  'Какие основные выводы в документе?',
]

export default function App() {
  const [health, setHealth] = useState(null)
  const [docs, setDocs] = useState([])
  const [selected, setSelected] = useState([])     // doc ids used as search scope
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [answerLang, setAnswerLang] = useState('')
  const [busy, setBusy] = useState(false)
  const [viewer, setViewer] = useState(null)        // {source} to show
  const [summaryDoc, setSummaryDoc] = useState(null)
  const endRef = useRef(null)
  const abortRef = useRef(null)

  const refresh = async () => {
    try { setDocs(await api.documents()) } catch {}
    try { setHealth(await api.health()) } catch { setHealth(null) }
  }
  useEffect(() => { refresh(); const t = setInterval(() => api.health().then(setHealth).catch(() => setHealth(null)), 15000); return () => clearInterval(t) }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const updateLast = (fn) => setMessages((m) => [...m.slice(0, -1), fn(m[m.length - 1])])

  const ask = async (q) => {
    const question = (q ?? input).trim()
    if (!question || busy) return
    setInput('')
    setBusy(true)
    setMessages((m) => [...m, { role: 'user', text: question },
      { role: 'assistant', text: '', sources: [], pending: true }])
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      await streamNDJSON('/api/ask', {
        question, doc_ids: selected.length ? selected : null, answer_lang: answerLang || null,
      }, (ev) => {
        if (ev.type === 'sources') updateLast((x) => ({ ...x, sources: ev.sources, lang: ev.lang, retrieval_ms: ev.retrieval_ms }))
        else if (ev.type === 'token') updateLast((x) => ({ ...x, text: x.text + ev.text }))
        else if (ev.type === 'error') updateLast((x) => ({ ...x, error: ev.message }))
        else if (ev.type === 'done') updateLast((x) => ({ ...x, pending: false, total_ms: ev.total_ms }))
      }, ctrl.signal)
    } catch (e) {
      if (e.name !== 'AbortError') updateLast((x) => ({ ...x, error: e.message }))
    } finally {
      updateLast((x) => ({ ...x, pending: false }))
      setBusy(false)
    }
  }

  const llmOk = health?.llm?.running && health?.llm?.model_available

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">Q</span>
          <div>
            <h1>DocQA</h1>
            <p>Multilingual Document Question Answering · EN · AR · RU</p>
          </div>
        </div>
        <div className="status">
          <span className={`pill ${health ? 'ok' : 'bad'}`} title="Embedding model used for semantic search">
            ● Embeddings: {health ? `${health.embedding_model}${health.fine_tuned ? ' (fine-tuned)' : ''}` : 'backend offline'}
          </span>
          <span className={`pill ${llmOk ? 'ok' : 'bad'}`} title="Local LLM served by Ollama">
            ● LLM: {health?.llm?.model || '—'} {health && !health.llm.running ? '(Ollama not running)' : health && !llmOk ? '(model not pulled)' : ''}
          </span>
        </div>
      </header>

      <div className="layout">
        <Sidebar docs={docs} selected={selected} setSelected={setSelected}
          onChange={refresh} onSummary={setSummaryDoc} onOpen={(d) => setViewer({ doc_id: d.id, filename: d.filename, page: 1, ext: d.ext })} />

        <main className="chat">
          <div className="messages">
            {messages.length === 0 && (
              <div className="empty">
                <h2>Ask anything about your documents</h2>
                <p>Upload PDF, DOCX or TXT files in English, Arabic or Russian, then ask in any of these languages.
                  Answers are generated only from the document text and cite the page they came from.</p>
                <div className="examples">
                  {EXAMPLES.map((e) => <button key={e} dir="auto" onClick={() => ask(e)} disabled={!docs.length}>{e}</button>)}
                </div>
                {!docs.length && <p className="hint">← Start by uploading a document.</p>}
              </div>
            )}
            {messages.map((m, i) => <Message key={i} m={m} onSource={(s) => setViewer({ ...s, ext: docs.find((d) => d.id === s.doc_id)?.ext })} />)}
            <div ref={endRef} />
          </div>

          <form className="composer" onSubmit={(e) => { e.preventDefault(); ask() }}>
            <div className="scope">
              <span>Searching: <b>{selected.length ? `${selected.length} selected document(s)` : 'all documents'}</b></span>
              <label>Answer in:
                <select value={answerLang} onChange={(e) => setAnswerLang(e.target.value)}>
                  {LANGS.map((l) => <option key={l.v} value={l.v}>{l.label}</option>)}
                </select>
              </label>
            </div>
            <div className="row">
              <textarea dir="auto" rows={2} value={input} placeholder={docs.length ? 'Ask a question… / اطرح سؤالاً… / Задайте вопрос…' : 'Upload a document first'}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() } }} />
              {busy
                ? <button type="button" className="btn stop" onClick={() => abortRef.current?.abort()}>Stop</button>
                : <button className="btn primary" disabled={!input.trim() || !docs.length}>Ask</button>}
            </div>
          </form>
        </main>
      </div>

      {viewer && <Viewer source={viewer} onClose={() => setViewer(null)} />}
      {summaryDoc && <SummaryPanel doc={summaryDoc} onClose={() => { setSummaryDoc(null); refresh() }} />}
    </div>
  )
}
