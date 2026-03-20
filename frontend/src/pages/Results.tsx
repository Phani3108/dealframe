import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Clock, FileVideo, AlertTriangle, TrendingUp } from 'lucide-react'
import { SegmentCard } from '../components/SegmentCard'
import { getJob, type Job } from '../api/client'

function RiskMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score > 0.6 ? 'bg-red-500' : score > 0.3 ? 'bg-amber-400' : 'bg-emerald-500'
  const textColor = score > 0.6 ? 'text-red-600' : score > 0.3 ? 'text-amber-600' : 'text-emerald-600'
  return (
    <div className="text-right">
      <p className="text-xs text-slate-500 mb-1">Overall risk</p>
      <p className={`text-3xl font-bold tabular-nums ${textColor}`}>{pct}%</p>
      <div className="w-24 h-1.5 bg-slate-100 rounded-full mt-1.5 ml-auto overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Results() {
  const { jobId } = useParams<{ jobId: string }>()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!jobId) return
    getJob(jobId)
      .then(setJob)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [jobId])

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-400">
        <div className="w-4 h-4 border-2 border-slate-300 border-t-indigo-500 rounded-full animate-spin" />
        Loading results…
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="p-8">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <div className="card p-8 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-slate-600">{error || 'Job not found'}</p>
        </div>
      </div>
    )
  }

  const intel = job.result
  const segments = intel?.segments ?? []
  const highRiskCount = segments.filter(p => p.extraction.risk === 'high').length

  return (
    <div className="p-8 max-w-4xl">
      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6 group">
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Dashboard
      </Link>

      {/* Header card */}
      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <FileVideo className="w-5 h-5 text-indigo-500" />
              <h1 className="text-lg font-bold text-slate-900">Analysis Results</h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-500 font-mono">
              <span>{jobId}</span>
              {intel && (
                <span className="flex items-center gap-1 font-sans">
                  <Clock className="w-3.5 h-3.5" />
                  {Math.round((intel.duration_ms ?? 0) / 1000)}s
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-6">
            {highRiskCount > 0 && (
              <div className="text-right">
                <p className="text-xs text-slate-500">High risk segments</p>
                <p className="text-3xl font-bold text-red-600 tabular-nums">{highRiskCount}</p>
              </div>
            )}
            {intel?.overall_risk_score != null && (
              <RiskMeter score={intel.overall_risk_score} />
            )}
          </div>
        </div>
      </div>

      {/* Status */}
      {job.status !== 'completed' ? (
        <div className="card p-10 text-center">
          <p className="text-slate-500">
            Status: <span className="font-semibold text-slate-800 capitalize">{job.status}</span>
          </p>
          {job.status === 'failed' && job.error && (
            <p className="text-sm text-red-600 mt-2">{job.error}</p>
          )}
        </div>
      ) : segments.length === 0 ? (
        <div className="card p-10 text-center">
          <TrendingUp className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="text-slate-400 text-sm">No segments found in this video.</p>
        </div>
      ) : (
        <>
          {/* Summary strip */}
          <div className="flex items-center gap-6 mb-4 text-sm text-slate-500">
            <span>{segments.length} segment{segments.length !== 1 ? 's' : ''} analyzed</span>
            {highRiskCount > 0 && (
              <span className="flex items-center gap-1 text-red-600 font-medium">
                <AlertTriangle className="w-3.5 h-3.5" />
                {highRiskCount} high risk
              </span>
            )}
            <span className="ml-auto">
              Scroll to explore
            </span>
          </div>

          <div className="space-y-3">
            {segments.map((pair, i) => (
              <SegmentCard key={i} pair={pair} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
