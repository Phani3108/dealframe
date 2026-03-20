import { useState, useEffect, useCallback } from 'react'
import { Cpu, CheckCircle2, XCircle, RefreshCw, Upload as UploadIcon, Zap } from 'lucide-react'
import { Badge } from '../components/Badge'
import {
  getLocalStatus,
  processLocally,
  getLocalJob,
  listLocalJobs,
  type LocalStatus,
} from '../api/client'

interface LocalJob {
  job_id: string
  status: string
  error?: string
  result?: {
    extraction_model: string
    total_latency_ms: number
    stage_latencies_ms: Record<string, number>
  }
}

function ModelStatusRow({
  label,
  available,
  detail,
}: {
  label: string
  available: boolean
  detail?: string
}) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-100 last:border-0">
      <div>
        <p className="text-sm font-medium text-slate-800">{label}</p>
        {detail && <p className="text-xs text-slate-400">{detail}</p>}
      </div>
      {available ? (
        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
      ) : (
        <XCircle className="w-4 h-4 text-slate-300" />
      )}
    </div>
  )
}

export function LocalPipeline() {
  const [status, setStatus] = useState<LocalStatus | null>(null)
  const [jobs, setJobs] = useState<LocalJob[]>([])
  const [loading, setLoading] = useState(true)
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [pollingId, setPollingId] = useState<string | null>(null)
  const [polledJob, setPolledJob] = useState<LocalJob | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.allSettled([
      getLocalStatus().then(setStatus).catch(() => {}),
      listLocalJobs().then(r => setJobs((r.jobs ?? []) as LocalJob[])).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  // Poll submitted job
  useEffect(() => {
    if (!pollingId) return
    const interval = setInterval(async () => {
      const j = await getLocalJob(pollingId).catch(() => null) as LocalJob | null
      if (!j) return
      setPolledJob(j)
      setJobs(prev => {
        const exists = prev.find(x => x.job_id === pollingId)
        return exists ? prev.map(x => x.job_id === pollingId ? { ...x, ...j } : x) : [{ ...j, job_id: pollingId }, ...prev]
      })
      if (j.status === 'completed' || j.status === 'failed') {
        setPollingId(null)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [pollingId])

  const handleProcess = async () => {
    if (!file) return
    setSubmitting(true)
    setPolledJob(null)
    try {
      const res = await processLocally(file)
      setPollingId(res.job_id)
      setFile(null)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to start processing')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">Local Pipeline</h1>
          <p className="page-subtitle">Process videos offline — zero API calls, zero cost</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-1.5">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Status panel */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-500" />
              Model Status
            </h2>
            {status ? (
              <>
                <ModelStatusRow
                  label="Whisper ASR"
                  available={status.whisper_available}
                  detail={`Model: ${status.whisper_model}`}
                />
                <ModelStatusRow
                  label="Qwen-VL Vision"
                  available={status.qwen_vl_available}
                  detail="Qwen2.5-VL-7B"
                />
                <ModelStatusRow
                  label="Fine-tuned Adapter"
                  available={status.finetuned_adapter_available}
                  detail={status.adapter_path ?? 'Not configured'}
                />
                <div className="mt-4 pt-3 border-t border-slate-100">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Active extractor</span>
                    <span className="font-semibold text-slate-800 capitalize">{status.active_extractor}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm mt-1.5">
                    <span className="text-slate-500">Cost per video</span>
                    <span className="font-semibold text-emerald-600">${status.cost_per_video_usd.toFixed(2)}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="py-4 text-center text-sm text-slate-400">
                Loading status…
              </div>
            )}
          </div>

          {/* Upload form */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-500" />
              Process Locally
            </h2>
            <label className={`block border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors mb-3 ${
              file ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 hover:border-slate-300'
            }`}>
              <input
                type="file"
                accept="video/*"
                className="hidden"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
              />
              {file ? (
                <p className="text-sm font-medium text-slate-800 truncate">{file.name}</p>
              ) : (
                <>
                  <UploadIcon className="w-6 h-6 text-slate-300 mx-auto mb-1" />
                  <p className="text-xs text-slate-500">Select video</p>
                </>
              )}
            </label>
            <button
              onClick={handleProcess}
              disabled={!file || submitting || !!pollingId}
              className="btn-primary w-full py-2.5"
            >
              {submitting ? 'Uploading…' : pollingId ? 'Processing…' : 'Run Local Pipeline'}
            </button>

            {pollingId && (
              <div className="mt-3 flex items-center gap-2 text-xs text-indigo-600">
                <div className="w-3 h-3 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                Polling job {pollingId.slice(0, 8)}…
              </div>
            )}
          </div>
        </div>

        {/* Jobs table */}
        <div className="col-span-2 space-y-4">
          {/* Polled result detail */}
          {polledJob && polledJob.status === 'completed' && polledJob.result && (
            <div className="card p-5 border-emerald-200 bg-emerald-50">
              <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mb-3">
                Latest Result
              </p>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-slate-500">Extractor</p>
                  <p className="font-semibold text-slate-800 capitalize">{polledJob.result.extraction_model}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Total latency</p>
                  <p className="font-semibold text-slate-800 tabular-nums">{polledJob.result.total_latency_ms}ms</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">API cost</p>
                  <p className="font-semibold text-emerald-600">$0.00</p>
                </div>
              </div>
              {Object.keys(polledJob.result.stage_latencies_ms).length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {Object.entries(polledJob.result.stage_latencies_ms).map(([stage, ms]) => (
                    <div key={stage} className="text-xs">
                      <span className="text-slate-500 capitalize">{stage.replace(/_ms$/, '').replace(/_/g, ' ')}</span>
                      {': '}
                      <span className="font-semibold text-slate-700 tabular-nums">{ms}ms</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Jobs list */}
          <div className="card">
            <div className="px-5 py-4 border-b border-slate-100">
              <h2 className="text-sm font-semibold text-slate-900">Local Jobs</h2>
            </div>
            {jobs.length === 0 ? (
              <div className="p-10 text-center">
                <Cpu className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                <p className="text-sm text-slate-400">No local jobs yet</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {jobs.slice(0, 10).map(job => (
                  <div key={job.job_id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <p className="text-sm font-mono text-slate-700">{job.job_id.slice(0, 16)}…</p>
                      {job.status === 'completed' && job.result && (
                        <p className="text-xs text-slate-400 mt-0.5">
                          {job.result.extraction_model} · {job.result.total_latency_ms}ms
                        </p>
                      )}
                      {job.error && (
                        <p className="text-xs text-red-500 mt-0.5">{job.error}</p>
                      )}
                    </div>
                    <Badge label={job.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
