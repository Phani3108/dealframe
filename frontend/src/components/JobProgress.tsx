import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, XCircle, AlertCircle } from 'lucide-react'
import { streamJobProgress, type JobProgressEvent, type SSESubscription } from '../api/client'

interface Props {
  jobId: string
  onComplete?: () => void
}

const STAGE_ORDER = ['enqueued', 'ingest', 'transcribe', 'diarize', 'align', 'extract', 'done'] as const
type StageId = typeof STAGE_ORDER[number]

const STAGE_LABEL: Record<StageId, string> = {
  enqueued: 'Queued',
  ingest: 'Extracting frames',
  transcribe: 'Transcribing audio',
  diarize: 'Diarizing speakers',
  align: 'Aligning timeline',
  extract: 'Extracting intelligence',
  done: 'Completed',
}

type StageStatus = 'idle' | 'active' | 'done' | 'error'

/**
 * Real-time pipeline progress card — consumes SSE events from the durable
 * worker queue and shows per-stage progress bars + recent log lines.
 */
export function JobProgress({ jobId, onComplete }: Props) {
  const [stages, setStages] = useState<Record<StageId, { status: StageStatus; pct?: number; detail?: unknown }>>(
    Object.fromEntries(STAGE_ORDER.map(s => [s, { status: 'idle' }])) as Record<StageId, { status: StageStatus }>,
  )
  const [log, setLog] = useState<JobProgressEvent[]>([])
  const [overall, setOverall] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let sub: SSESubscription | null = null
    setStages(Object.fromEntries(STAGE_ORDER.map(s => [s, { status: 'idle' }])) as Record<StageId, { status: StageStatus }>)
    setLog([])
    setOverall(0)
    setError(null)

    sub = streamJobProgress(jobId, (event, data) => {
      if (event === 'ready' || event === 'keepalive') return

      const stage = (data.stage ?? event) as StageId | 'failed'
      const status = data.status ?? 'info'

      setLog(l => [...l.slice(-40), data])

      if (stage === 'failed') {
        const msg = (data.detail as { message?: string })?.message ?? 'Pipeline failed'
        setError(msg)
        setStages(prev => {
          const next = { ...prev }
          for (const s of STAGE_ORDER) {
            if (next[s].status === 'active') next[s] = { status: 'error' }
          }
          return next
        })
        return
      }

      if (stage in STAGE_LABEL) {
        setStages(prev => {
          const next = { ...prev }
          const idx = STAGE_ORDER.indexOf(stage)
          for (let i = 0; i < idx; i++) {
            if (next[STAGE_ORDER[i]].status !== 'done') next[STAGE_ORDER[i]] = { status: 'done' }
          }
          const pct = (data.detail as { pct?: number })?.pct
          if (status === 'done') next[stage] = { status: 'done', pct: 100, detail: data.detail }
          else next[stage] = { status: 'active', pct, detail: data.detail }
          return next
        })
        const pct = (data.detail as { pct?: number })?.pct
        if (typeof pct === 'number') setOverall(pct)

        if (stage === 'done' && status === 'done') {
          setOverall(100)
          onComplete?.()
        }
      }
    })
    return () => { sub?.close() }
  }, [jobId])

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-4 bg-gradient-to-r from-indigo-50 to-violet-50 border-b border-slate-100">
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-slate-800">Live pipeline progress</p>
          <span className="font-mono text-[11px] text-slate-500">{jobId.slice(0, 8)}</span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-white/60 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
            style={{ width: `${Math.min(100, Math.max(overall, 2))}%` }}
          />
        </div>
        <p className="text-[10px] font-mono text-slate-500 mt-1.5">{overall}%</p>
      </div>

      <div className="p-5 space-y-3">
        {STAGE_ORDER.filter(s => s !== 'enqueued' || stages[s].status !== 'idle').map((s) => {
          const state = stages[s]
          return (
            <div key={s} className="flex items-center gap-3">
              <div className="flex-shrink-0">
                {state.status === 'done' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                {state.status === 'active' && <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />}
                {state.status === 'error' && <XCircle className="w-5 h-5 text-red-500" />}
                {state.status === 'idle' && (
                  <div className="w-5 h-5 rounded-full border-2 border-slate-200" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${
                    state.status === 'active' ? 'text-indigo-600 font-semibold' :
                    state.status === 'done' ? 'text-slate-700' :
                    state.status === 'error' ? 'text-red-600' : 'text-slate-400'
                  }`}>
                    {STAGE_LABEL[s]}
                  </span>
                  {state.status === 'done' && (
                    <span className="text-[10px] text-emerald-500 font-medium">Done</span>
                  )}
                </div>
                {state.pct != null && state.status === 'active' && (
                  <div className="mt-1 h-1 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-indigo-400 transition-all" style={{ width: `${state.pct}%` }} />
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {error && (
          <div className="mt-2 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl px-3 py-2 text-sm text-red-700">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {log.length > 0 && (
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-slate-400 hover:text-slate-600">
              Event log ({log.length})
            </summary>
            <div className="mt-2 max-h-40 overflow-y-auto font-mono text-[10px] text-slate-500 space-y-0.5 bg-slate-50 rounded-lg p-2">
              {log.slice().reverse().map((e, i) => (
                <div key={i}>
                  <span className="text-indigo-400">{e.stage}</span>
                  <span className="text-slate-400"> · {e.status}</span>
                  {Object.keys(e.detail || {}).length > 0 && (
                    <span className="text-slate-500"> · {JSON.stringify(e.detail)}</span>
                  )}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}
