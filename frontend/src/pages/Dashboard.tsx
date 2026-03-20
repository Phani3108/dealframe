import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileVideo, AlertTriangle, Cpu, DollarSign, ArrowRight, RefreshCw } from 'lucide-react'
import { StatCard } from '../components/StatCard'
import { Badge } from '../components/Badge'
import {
  listJobs,
  getObjections,
  getRiskSummary,
  getLocalStatus,
  type Job,
  type Objection,
  type RiskSummary,
  type LocalStatus,
} from '../api/client'

export function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [objections, setObjections] = useState<Objection[]>([])
  const [riskSummary, setRiskSummary] = useState<RiskSummary | null>(null)
  const [localStatus, setLocalStatus] = useState<LocalStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.allSettled([
      listJobs().then(r => setJobs(r.jobs ?? [])).catch(() => {}),
      getObjections(5).then(r => setObjections(r.objections ?? [])).catch(() => {}),
      getRiskSummary().then(setRiskSummary).catch(() => {}),
      getLocalStatus().then(setLocalStatus).catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const completedJobs = jobs.filter(j => j.status === 'completed').length
  const highRisk = riskSummary?.high ?? 0

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Video decision intelligence at a glance</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={load}
            className="btn-secondary flex items-center gap-1.5"
            disabled={loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link to="/upload" className="btn-primary flex items-center gap-1.5">
            <FileVideo className="w-3.5 h-3.5" />
            Upload Video
          </Link>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Videos Processed"
          value={completedJobs}
          icon={FileVideo}
          iconBg="bg-indigo-50"
          iconColor="text-indigo-600"
        />
        <StatCard
          label="High Risk Segments"
          value={highRisk}
          icon={AlertTriangle}
          iconBg={highRisk > 0 ? 'bg-red-50' : 'bg-slate-50'}
          iconColor={highRisk > 0 ? 'text-red-500' : 'text-slate-400'}
          trendPositive={highRisk === 0}
        />
        <StatCard
          label="Active Extractor"
          value={localStatus?.active_extractor ?? '—'}
          icon={Cpu}
          iconBg="bg-slate-50"
          iconColor="text-slate-600"
          trend={localStatus?.finetuned_adapter_available ? 'Fine-tuned' : 'Rule-based'}
          trendPositive={localStatus?.finetuned_adapter_available}
        />
        <StatCard
          label="API Cost This Session"
          value="$0.00"
          icon={DollarSign}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          trend="Local pipeline"
          trendPositive
        />
      </div>

      {/* Bottom grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent jobs */}
        <div className="col-span-2 card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-900">Recent Jobs</h2>
            <Link to="/upload" className="text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1 font-medium">
              New upload <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {jobs.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <FileVideo className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-400">No videos processed yet.</p>
              <Link to="/upload" className="text-sm text-indigo-600 hover:underline mt-1 inline-block">
                Upload your first video →
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {jobs.slice(0, 8).map(job => (
                <Link
                  key={job.job_id}
                  to={`/results/${job.job_id}`}
                  className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileVideo className="w-4 h-4 text-slate-300 flex-shrink-0" />
                    <span className="text-sm text-slate-700 font-mono truncate">
                      {job.job_id.slice(0, 16)}…
                    </span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <Badge label={job.status} />
                    <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Top objections */}
        <div className="card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-900">Top Objections</h2>
            <Link to="/intelligence" className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
              View all
            </Link>
          </div>
          {objections.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm text-slate-400">No data yet</p>
              <p className="text-xs text-slate-300 mt-1">Process videos to see patterns</p>
            </div>
          ) : (
            <div className="p-5 space-y-4">
              {objections.map((obj, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-slate-700 truncate pr-3 font-medium">{obj.text}</span>
                    <span className="text-slate-400 flex-shrink-0 tabular-nums">×{obj.count}</span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-400 rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (obj.count / (objections[0]?.count || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="mt-6 grid grid-cols-3 gap-4">
        {[
          { to: '/observatory', label: 'Compare Models', sub: 'Run multi-model analysis', color: 'border-purple-200 hover:border-purple-300 hover:bg-purple-50' },
          { to: '/intelligence', label: 'View Intelligence', sub: 'Objections & trends', color: 'border-indigo-200 hover:border-indigo-300 hover:bg-indigo-50' },
          { to: '/local', label: 'Local Pipeline', sub: 'Process without API calls', color: 'border-emerald-200 hover:border-emerald-300 hover:bg-emerald-50' },
        ].map(({ to, label, sub, color }) => (
          <Link
            key={to}
            to={to}
            className={`border rounded-xl p-4 transition-colors ${color}`}
          >
            <p className="text-sm font-semibold text-slate-900">{label}</p>
            <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
