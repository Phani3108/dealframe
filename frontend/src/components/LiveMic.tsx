import { useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Radio, AlertTriangle, Sparkles, Zap, Activity, TrendingUp } from 'lucide-react'

export interface LiveCue {
  id: string
  type: string
  title: string
  message: string
  priority?: string
  ts_ms?: number
}

export interface LiveTranscriptSegment {
  id: string
  ts_ms: number
  text: string
  is_final: boolean
}

interface Props {
  onCue?: (cue: LiveCue) => void
  onTranscript?: (seg: LiveTranscriptSegment) => void
}

/**
 * Captures microphone audio in the browser, resamples to 16 kHz / 16-bit / mono PCM,
 * and streams it to `/ws/live-copilot`. Renders live transcript + cue cards.
 *
 * Uses a Web Audio ScriptProcessor (broadly supported) because raw PCM is required
 * by the backend streaming ASR, and MediaRecorder only yields compressed frames.
 */
export function LiveMic({ onCue, onTranscript }: Props) {
  const [recording, setRecording] = useState(false)
  const [level, setLevel] = useState(0)
  const [status, setStatus] = useState<'idle' | 'connecting' | 'live' | 'error'>('idle')
  const [error, setError] = useState('')
  const [transcript, setTranscript] = useState<LiveTranscriptSegment[]>([])
  const [cues, setCues] = useState<LiveCue[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const procRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stop = () => {
    try { procRef.current?.disconnect() } catch { /* noop */ }
    try { sourceRef.current?.disconnect() } catch { /* noop */ }
    try { ctxRef.current?.close() } catch { /* noop */ }
    streamRef.current?.getTracks().forEach(t => t.stop())
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try { wsRef.current.send(JSON.stringify({ type: 'end' })) } catch { /* noop */ }
      try { wsRef.current.close() } catch { /* noop */ }
    }
    wsRef.current = null
    ctxRef.current = null
    procRef.current = null
    sourceRef.current = null
    streamRef.current = null
    setRecording(false)
    setStatus('idle')
    setLevel(0)
  }

  useEffect(() => () => stop(), [])

  const start = async () => {
    setError('')
    setStatus('connecting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      streamRef.current = stream

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/live-copilot`)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => setStatus('live')
      ws.onerror = () => { setStatus('error'); setError('WebSocket connection failed') }
      ws.onclose = () => { if (status !== 'error') setStatus('idle') }
      ws.onmessage = ev => {
        try {
          const msg = JSON.parse(typeof ev.data === 'string' ? ev.data : '')
          if (msg.type === 'transcript') {
            const seg: LiveTranscriptSegment = {
              id: `${msg.ts_ms}-${Math.random().toString(36).slice(2, 6)}`,
              ts_ms: msg.ts_ms ?? 0,
              text: msg.text ?? '',
              is_final: !!msg.is_final,
            }
            setTranscript(prev => [...prev.slice(-80), seg])
            onTranscript?.(seg)
          } else if (msg.type === 'cue') {
            const cue: LiveCue = {
              id: `${msg.ts_ms}-${Math.random().toString(36).slice(2, 6)}`,
              type: msg.cue?.type ?? 'hint',
              title: msg.cue?.title ?? 'Cue',
              message: msg.cue?.message ?? '',
              priority: msg.cue?.priority,
              ts_ms: msg.ts_ms,
            }
            setCues(prev => [cue, ...prev.slice(0, 19)])
            onCue?.(cue)
          }
        } catch { /* ignore non-JSON */ }
      }

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      const ctx: AudioContext = new AudioCtx()
      ctxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      sourceRef.current = source
      // 4096-sample buffer keeps UI responsive while minimising overhead
      const proc = ctx.createScriptProcessor(4096, 1, 1)
      procRef.current = proc

      proc.onaudioprocess = e => {
        const input = e.inputBuffer.getChannelData(0)
        // naive level meter
        let peak = 0
        for (let i = 0; i < input.length; i++) {
          const a = Math.abs(input[i])
          if (a > peak) peak = a
        }
        setLevel(peak)

        // downsample from ctx.sampleRate → 16000 Hz
        const srcRate = ctx.sampleRate
        const ratio = srcRate / 16000
        const outLen = Math.floor(input.length / ratio)
        const pcm = new Int16Array(outLen)
        for (let i = 0; i < outLen; i++) {
          const s = input[Math.floor(i * ratio)]
          const clipped = Math.max(-1, Math.min(1, s))
          pcm[i] = clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff
        }
        if (ws.readyState === WebSocket.OPEN) {
          try { ws.send(pcm.buffer) } catch { /* ignore */ }
        }
      }

      source.connect(proc)
      proc.connect(ctx.destination)
      setRecording(true)
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Microphone access denied')
      stop()
    }
  }

  const cueColor = (type: string) => {
    if (type.includes('risk') || type.includes('warning')) return 'border-red-400 bg-red-50 text-red-900'
    if (type.includes('objection')) return 'border-amber-400 bg-amber-50 text-amber-900'
    if (type.includes('closing') || type.includes('decision')) return 'border-emerald-400 bg-emerald-50 text-emerald-900'
    if (type.includes('battlecard')) return 'border-violet-400 bg-violet-50 text-violet-900'
    return 'border-blue-400 bg-blue-50 text-blue-900'
  }

  const cueIcon = (type: string) => {
    if (type.includes('risk') || type.includes('warning')) return AlertTriangle
    if (type.includes('objection')) return AlertTriangle
    if (type.includes('closing') || type.includes('decision')) return Sparkles
    if (type.includes('pace')) return TrendingUp
    return Zap
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Mic + transcript panel */}
      <div className="card p-4 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-indigo-500" />
            <h3 className="text-sm font-bold text-slate-700">Live mic stream</h3>
          </div>
          <span className={`flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold ${
            status === 'live' ? 'text-emerald-600' : status === 'error' ? 'text-red-600' : 'text-slate-400'
          }`}>
            <Radio className={`w-3 h-3 ${status === 'live' ? 'animate-pulse' : ''}`} />
            {status}
          </span>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={recording ? stop : start}
            className={`w-11 h-11 rounded-full flex items-center justify-center shadow transition ${
              recording ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-indigo-500 text-white hover:bg-indigo-600'
            }`}
            aria-label={recording ? 'Stop recording' : 'Start recording'}
          >
            {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
          <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-400 to-violet-500 transition-all"
              style={{ width: `${Math.min(100, level * 200)}%` }}
            />
          </div>
          <span className="font-mono text-xs text-slate-500 w-10 text-right">{Math.round(level * 100)}</span>
        </div>

        {error && (
          <div className="mb-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>
        )}

        <div className="flex-1 min-h-[160px] max-h-[360px] overflow-y-auto rounded-lg bg-slate-50 border border-slate-100 p-3 text-sm leading-relaxed">
          {transcript.length === 0 ? (
            <p className="text-slate-400 italic text-xs">Transcript will stream here once you start speaking…</p>
          ) : (
            transcript.map(s => (
              <span key={s.id} className={s.is_final ? 'text-slate-800' : 'text-slate-400'}>
                {s.text}{' '}
              </span>
            ))
          )}
        </div>
      </div>

      {/* Cue cards */}
      <div className="card p-4 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <h3 className="text-sm font-bold text-slate-700">Negotiation cues</h3>
          </div>
          {cues.length > 0 && (
            <button onClick={() => setCues([])} className="text-[10px] text-slate-400 hover:text-slate-600">Clear</button>
          )}
        </div>
        <div className="flex-1 min-h-[160px] max-h-[360px] overflow-y-auto space-y-2">
          {cues.length === 0 ? (
            <div className="flex items-center justify-center h-full text-center">
              <p className="text-xs text-slate-400">Cues will pop in here as the model detects risk, objections, and closing moments.</p>
            </div>
          ) : (
            cues.map(c => {
              const Icon = cueIcon(c.type)
              return (
                <div key={c.id} className={`rounded-lg border-l-4 p-3 ${cueColor(c.type)}`}>
                  <div className="flex items-center gap-2 mb-0.5">
                    <Icon className="w-3.5 h-3.5" />
                    <span className="text-[10px] font-bold uppercase tracking-wider">{c.type.replace('_', ' ')}</span>
                    {c.priority && <span className="ml-auto text-[10px] font-mono opacity-70">{c.priority}</span>}
                  </div>
                  <p className="text-xs font-semibold mt-0.5">{c.title}</p>
                  <p className="text-xs opacity-90 leading-snug mt-0.5">{c.message}</p>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
