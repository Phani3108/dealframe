import { useState, useEffect, useCallback } from 'react'
import { Eye, Upload as UploadIcon, RefreshCw, FileVideo } from 'lucide-react'
import { Badge } from '../components/Badge'
import {
  listObservatorySessions,
  getObservatorySession,
  startObservatory,
  type ObservatorySession,
} from '../api/client'

function AgreementBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const bg = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${bg} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-slate-700 w-10 text-right">{pct}%</span>
    </div>
  )
}

export function Observatory() {
  const [sessions, setSessions] = useState<ObservatorySession[]>([])
  const [selected, setSelected] = useState<ObservatorySession | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [polling, setPolling] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    listObservatorySessions()
      .then(r => setSessions(r.sessions ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  // Poll active session
  useEffect(() => {
    if (!polling) return
    const interval = setInterval(async () => {
      const s = await getObservatorySession(polling).catch(() => null)
      if (!s) return
      setSessions(prev => prev.map(x => x.session_id === polling ? s : x))
      if (s.status === 'completed' || s.status === 'failed') {
        setPolling(null)
        setSelected(s)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [polling])

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true)
    try {
      const res = await startObservatory(file)
      setPolling(res.session_id)
      load()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to start observatory')
    } finally {
      setUploading(false)
      setFile(null)
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">Model Observatory</h1>
          <p className="page-subtitle">Compare GPT-4o, Claude, and Qwen2.5-VL on the same video</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-1.5">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Upload form */}
        <div className="col-span-1">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Eye className="w-4 h-4 text-indigo-500" />
              Start Comparison
            </h2>
            <label className={`block border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors mb-4 ${
              file ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 hover:border-slate-300'
            }`}>
              <input
                type="file"
                accept="video/*"
                className="hidden"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
              />
              {file ? (
                <>
                  <FileVideo className="w-8 h-8 text-emerald-500 mx-auto mb-1" />
                  <p className="text-sm font-medium text-slate-800">{file.name}</p>
                </>
              ) : (
                <>
                  <UploadIcon className="w-8 h-8 text-slate-300 mx-auto mb-1" />
                  <p className="text-sm text-slate-500">Click to select video</p>
                </>
              )}
            </label>
            <button
              onClick={handleSubmit}
              disabled={!file || uploading}
              className="btn-primary w-full py-2.5"
            >
              {uploading ? 'Starting…' : 'Run Observatory'}
            </button>
            {polling && (
              <div className="mt-3 flex items-center gap-2 text-xs text-indigo-600">
                <div className="w-3 h-3 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                Running comparison…
              </div>
            )}
          </div>
        </div>

        {/* Sessions list */}
        <div className="col-span-2">
          <div className="card">
            <div className="px-5 py-4 border-b border-slate-100">
              <h2 className="text-sm font-semibold text-slate-900">Sessions</h2>
            </div>
            {sessions.length === 0 ? (
              <div className="p-10 text-center">
                <Eye className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                <p className="text-sm text-slate-400">No comparison sessions yet</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {sessions.map(session => (
                  <button
                    key={session.session_id}
                    onClick={() => setSelected(session)}
                    className={`w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors text-left ${
                      selected?.session_id === session.session_id ? 'bg-indigo-50' : ''
                    }`}
                  >
                    <div>
                      <p className="text-sm font-mono text-slate-700">{session.session_id.slice(0, 16)}…</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {session.models?.join(' · ') ?? 'Unknown models'}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {session.report?.overall_agreement != null && (
                        <span className="text-xs text-slate-500">
                          {Math.round(session.report.overall_agreement * 100)}% agree
                        </span>
                      )}
                      <Badge label={session.status} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Session detail */}
          {selected?.report && (
            <div className="card mt-4 p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">
                Session detail — {selected.session_id.slice(0, 12)}
              </h3>

              <div className="mb-5">
                <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-3">
                  Overall agreement
                </p>
                <AgreementBar score={selected.report.overall_agreement} />
              </div>

              {Object.keys(selected.report.pairwise_topic_agreement ?? {}).length > 0 && (
                <div className="mb-5">
                  <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-3">
                    Pairwise topic agreement
                  </p>
                  <div className="space-y-2">
                    {Object.entries(selected.report.pairwise_topic_agreement).map(([pair, score]) => (
                      <div key={pair}>
                        <p className="text-xs text-slate-600 mb-1">{pair}</p>
                        <AgreementBar score={score} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(selected.report.model_stats ?? {}).length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-3">
                    Model performance
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-slate-400 font-medium">
                          <th className="text-left pb-2">Model</th>
                          <th className="text-right pb-2">Avg confidence</th>
                          <th className="text-right pb-2">Avg latency</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {Object.entries(selected.report.model_stats).map(([model, stats]) => (
                          <tr key={model}>
                            <td className="py-2 text-slate-700 font-medium">{model}</td>
                            <td className="py-2 text-right text-slate-600 tabular-nums">
                              {(stats.avg_confidence * 100).toFixed(0)}%
                            </td>
                            <td className="py-2 text-right text-slate-600 tabular-nums">
                              {stats.avg_latency_ms.toFixed(0)}ms
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
