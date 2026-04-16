import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Send, Sparkles, Loader2, Mic, MicOff, BookOpen, Volume2 } from 'lucide-react'
import {
  streamDealChat,
  listDealConversations,
  getConversationMessages,
  type ChatCitation,
  type ChatMessage,
  type SSESubscription,
} from '../api/client'

interface Props {
  jobId: string
  onCitationClick?: (timestamp: string, segmentIndex?: number) => void
}

interface UIMessage {
  role: 'user' | 'assistant'
  content: string
  citations: ChatCitation[]
  pending?: boolean
  model?: string
  latency_ms?: number
}

const SUGGESTIONS = [
  'What are the biggest objections in this call?',
  'Where was the deal most at risk?',
  'Give me the top decision signals with timestamps.',
  'Summarize the buyer\'s priorities.',
  'What should I do next?',
]

export function DealChat({ jobId, onCitationClick }: Props) {
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const subRef = useRef<SSESubscription | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    listDealConversations(jobId).then(d => {
      const first = d.conversations[0]
      if (first) {
        setConversationId(first.id)
        getConversationMessages(first.id).then(r => {
          setMessages(r.messages.map((m: ChatMessage) => ({
            role: m.role as 'user' | 'assistant',
            content: m.content,
            citations: m.citations ?? [],
            model: m.model,
            latency_ms: m.latency_ms,
          })))
        }).catch(() => {})
      }
    }).catch(() => {})
    return () => subRef.current?.close()
  }, [jobId])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const ask = (q?: string) => {
    const question = (q ?? input).trim()
    if (!question || streaming) return

    setInput('')
    setStreaming(true)

    setMessages(prev => [
      ...prev,
      { role: 'user', content: question, citations: [] },
      { role: 'assistant', content: '', citations: [], pending: true },
    ])

    const sub = streamDealChat(jobId, question, (event, data) => {
      if (event === 'meta') {
        const cid = (data as { conversation_id?: string }).conversation_id
        if (cid) setConversationId(cid)
      } else if (event === 'token') {
        const delta = (data as { delta?: string }).delta ?? ''
        setMessages(prev => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last && last.role === 'assistant') {
            next[next.length - 1] = { ...last, content: last.content + delta, pending: true }
          }
          return next
        })
      } else if (event === 'citations') {
        const citations = (data as { citations?: ChatCitation[] }).citations ?? []
        setMessages(prev => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last && last.role === 'assistant') {
            next[next.length - 1] = { ...last, citations }
          }
          return next
        })
      } else if (event === 'done') {
        const d = data as { latency_ms?: number; model?: string }
        setMessages(prev => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last && last.role === 'assistant') {
            next[next.length - 1] = { ...last, pending: false, model: d.model, latency_ms: d.latency_ms }
          }
          return next
        })
        setStreaming(false)
      } else if (event === 'error') {
        setMessages(prev => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last && last.role === 'assistant') {
            next[next.length - 1] = { ...last, content: `Error: ${(data as { message?: string }).message}`, pending: false }
          }
          return next
        })
        setStreaming(false)
      }
    }, conversationId ?? undefined)
    subRef.current = sub
    sub.done.finally(() => setStreaming(false))
  }

  const toggleVoice = async () => {
    if (recording) {
      mediaRef.current?.stop()
      setRecording(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const form = new FormData()
        form.append('file', blob, 'voice.webm')
        try {
          const res = await fetch(`/api/v1/chat/${jobId}/voice`, { method: 'POST', body: form })
          const data = await res.json()
          const transcript = (data.transcript as string | undefined)?.trim()
          if (transcript) ask(transcript)
        } catch { /* ignore */ }
      }
      mediaRef.current = rec
      rec.start()
      setRecording(true)
    } catch {
      /* microphone denied */
    }
  }

  const renderMessage = (text: string, citations: ChatCitation[]) => {
    // Turn [ts=MM:SS] markers into inline clickable pills.
    const parts = text.split(/(\[ts=[0-9:]+\])/g)
    return (
      <>
        {parts.map((p, i) => {
          const m = /^\[ts=([0-9:]+)\]$/.exec(p)
          if (m) {
            const ts = m[1]
            const cite = citations.find(c => c.timestamp.endsWith(ts) || c.timestamp === ts)
            return (
              <button
                key={i}
                onClick={() => onCitationClick?.(ts, cite?.segment_index)}
                className="inline-flex items-center gap-1 font-mono text-[11px] rounded-md bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/35 hover:text-indigo-200 px-1.5 py-0.5 mx-0.5 border border-indigo-400/30 transition-colors"
                title="Jump to this moment in the video"
              >
                <Volume2 className="w-3 h-3" />{ts}
              </button>
            )
          }
          return <span key={i}>{p}</span>
        })}
      </>
    )
  }

  return (
    <div className="flex flex-col h-full bg-white/90 backdrop-blur rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100 bg-gradient-to-r from-indigo-50 to-violet-50">
        <MessageSquare className="w-4 h-4 text-indigo-500" />
        <p className="text-sm font-bold text-slate-800">Chat with this deal</p>
        <span className="ml-auto text-[10px] text-slate-400 font-mono">
          {messages.length} message{messages.length === 1 ? '' : 's'}
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-sm text-slate-500">
              <Sparkles className="w-4 h-4 text-indigo-400 mt-0.5" />
              <p>Ask anything about this deal. Answers cite the exact moment and jump the video there.</p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="text-left text-[13px] px-3 py-2 rounded-lg border border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50 text-slate-600 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'flex justify-end' : ''}>
            <div
              className={`max-w-[90%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-tr-sm'
                  : 'bg-slate-50 text-slate-800 border border-slate-100 rounded-tl-sm'
              }`}
            >
              {m.role === 'assistant'
                ? renderMessage(m.content || (m.pending ? '…' : ''), m.citations)
                : m.content}
              {m.role === 'assistant' && m.pending && (
                <Loader2 className="inline-block w-3 h-3 ml-1 animate-spin text-indigo-400" />
              )}
              {m.role === 'assistant' && m.citations.length > 0 && !m.pending && (
                <div className="mt-3 pt-3 border-t border-slate-200/80">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1 mb-2">
                    <BookOpen className="w-3 h-3" /> Sources
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {m.citations.map((c, ci) => (
                      <button
                        key={ci}
                        onClick={() => onCitationClick?.(c.timestamp, c.segment_index)}
                        className="inline-flex items-center gap-1 text-[11px] bg-white border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 rounded-lg px-2 py-1 text-slate-700 transition-colors"
                      >
                        <span className="font-mono text-indigo-600">{c.timestamp}</span>
                        <span className="capitalize">{c.topic}</span>
                        <span className={`text-[10px] tabular-nums ${
                          c.risk_score > 0.6 ? 'text-red-500' : c.risk_score > 0.3 ? 'text-amber-500' : 'text-emerald-500'
                        }`}>{Math.round((c.risk_score ?? 0) * 100)}%</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {m.role === 'assistant' && m.model && !m.pending && (
                <p className="text-[9px] text-slate-400 mt-2 font-mono">
                  {m.model} · {m.latency_ms}ms
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="px-3 pb-3 pt-2 border-t border-slate-100 bg-slate-50/60">
        <div className="flex gap-2">
          <button
            onClick={toggleVoice}
            title={recording ? 'Stop recording' : 'Voice question'}
            className={`p-2.5 rounded-xl border transition-colors ${
              recording
                ? 'bg-red-500 text-white border-red-500 animate-pulse'
                : 'bg-white border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-300'
            }`}
          >
            {recording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
          <input
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
            placeholder={streaming ? 'Thinking…' : 'Ask about this deal…'}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() }
            }}
            disabled={streaming}
          />
          <button
            onClick={() => ask()}
            disabled={streaming || !input.trim()}
            className="px-4 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-40 transition-colors"
          >
            {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
