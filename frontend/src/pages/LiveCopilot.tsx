import { useState, useEffect, useRef } from 'react'
import { Bot, Send, Zap, RefreshCw, Radio, AlertTriangle, Sparkles, Mic, FileText } from 'lucide-react'
import { analyzeLive, getCopilotConfig } from '../api/client'
import { LiveMic } from '../components/LiveMic'

interface Signal {
  type: string
  text: string
  confidence?: number
  timestamp?: string
}

export function LiveCopilot() {
  const [transcript, setTranscript] = useState('')
  const [signals, setSignals] = useState<Signal[]>([])
  const [config, setConfig] = useState<{ signal_types: string[]; enabled: boolean; refresh_interval_ms: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'mic' | 'paste'>('mic')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getCopilotConfig().then(setConfig).catch(() => {})
  }, [])

  const analyze = async () => {
    if (!transcript.trim()) return
    setLoading(true)
    try {
      const res = await analyzeLive(transcript)
      const raw = res.signals
      const parsed: Signal[] = Array.isArray(raw)
        ? raw
        : typeof raw === 'object' && raw !== null
          ? Object.entries(raw).flatMap(([type, items]) =>
              Array.isArray(items) ? items.map((s: any) => ({ type, ...s })) : [{ type, text: String(items) }]
            )
          : []
      setSignals(prev => [...prev, ...parsed])
      setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }), 100)
    } catch { /* ignore */ }
    setLoading(false)
  }

  const signalColors: Record<string, string> = {
    objection: 'border-red-400 bg-red-50',
    risk: 'border-amber-400 bg-amber-50',
    intent: 'border-blue-400 bg-blue-50',
    decision: 'border-emerald-400 bg-emerald-50',
    question: 'border-violet-400 bg-violet-50',
  }

  const signalIcons: Record<string, typeof Zap> = {
    objection: AlertTriangle,
    risk: AlertTriangle,
    intent: Zap,
    decision: Sparkles,
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in h-[calc(100vh-2rem)] flex flex-col">
      {/* Header */}
      <div className="relative mb-6 bg-gradient-to-br from-blue-600 via-blue-700 to-cyan-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-blue-900/20 flex-shrink-0">
        <div className="relative flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-cyan-300 animate-pulse" />
              <span className="text-xs font-semibold text-blue-200 uppercase tracking-widest">Real-Time</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Live Copilot</h1>
            <p className="text-blue-200 text-sm mt-1">AI coaching signals as the conversation unfolds</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-white/10 rounded-lg p-0.5 gap-0.5">
              <button
                onClick={() => setMode('mic')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                  mode === 'mic' ? 'bg-white text-blue-700' : 'text-blue-100 hover:text-white'
                }`}
              >
                <Mic className="w-3.5 h-3.5" /> Live mic
              </button>
              <button
                onClick={() => setMode('paste')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                  mode === 'paste' ? 'bg-white text-blue-700' : 'text-blue-100 hover:text-white'
                }`}
              >
                <FileText className="w-3.5 h-3.5" /> Paste text
              </button>
            </div>
            {config && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white/10 rounded-lg text-xs text-blue-200">
                <Radio className="w-3.5 h-3.5" />
                {config.enabled ? 'Active' : 'Disabled'} · {config.signal_types.length} signals
              </div>
            )}
          </div>
        </div>
      </div>

      {mode === 'mic' ? (
        <div className="flex-1 min-h-0">
          <LiveMic />
        </div>
      ) : (
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0">
        {/* Left: Transcript input */}
        <div className="flex flex-col bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
            <Bot className="w-4 h-4 text-blue-500" />
            <span className="text-sm font-semibold text-slate-700">Transcript Feed</span>
          </div>
          <textarea
            value={transcript}
            onChange={e => setTranscript(e.target.value)}
            placeholder="Paste or type the call transcript here…&#10;&#10;Example: &quot;I'm not sure the pricing works for us. We had a bad experience with your competitor last quarter and need to see more ROI before committing.&quot;"
            className="flex-1 p-5 text-sm text-slate-700 resize-none focus:outline-none bg-slate-50/50 min-h-[200px]"
          />
          <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-slate-400">{transcript.split(/\s+/).filter(Boolean).length} words</span>
            <button
              onClick={analyze}
              disabled={loading || !transcript.trim()}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-40 transition"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {loading ? 'Analyzing…' : 'Analyze'}
            </button>
          </div>
        </div>

        {/* Right: Signals feed */}
        <div className="flex flex-col bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" />
              <span className="text-sm font-semibold text-slate-700">Coaching Signals</span>
            </div>
            {signals.length > 0 && (
              <button onClick={() => setSignals([])} className="text-xs text-slate-400 hover:text-slate-600 transition">Clear</button>
            )}
          </div>
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-3 min-h-[200px]">
            {signals.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Sparkles className="w-8 h-8 text-slate-300 mb-2" />
                <p className="text-sm text-slate-400">Signals will appear here as you analyze the transcript.</p>
              </div>
            ) : (
              signals.map((s, i) => {
                const Icon = signalIcons[s.type] ?? Zap
                return (
                  <div key={i} className={`rounded-lg border-l-4 p-4 ${signalColors[s.type] ?? 'border-slate-300 bg-slate-50'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="w-3.5 h-3.5" />
                      <span className="text-xs font-bold uppercase text-slate-600">{s.type}</span>
                      {s.confidence != null && (
                        <span className="ml-auto text-xs font-mono text-slate-400">{(s.confidence * 100).toFixed(0)}%</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-700">{s.text}</p>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
      )}
    </div>
  )
}
