import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Inbox, AlertTriangle, TrendingUp, Filter, ArrowUpRight, CheckCircle2, Loader2, XCircle, RefreshCw } from 'lucide-react'
import { listDeals, getDealSummary, type DealRow } from '../api/client'

function riskColor(score: number): string {
  if (score > 0.6) return 'from-red-500 to-red-600'
  if (score > 0.3) return 'from-amber-400 to-amber-500'
  return 'from-emerald-400 to-emerald-500'
}

export function DealInbox() {
  const [deals, setDeals] = useState<DealRow[]>([])
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof getDealSummary>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'high-risk' | 'processing' | 'completed'>('all')
  const [query, setQuery] = useState('')

  const refresh = () => {
    setLoading(true)
    Promise.all([
      listDeals(200).then(r => setDeals(r.deals)).catch(() => setDeals([])),
      getDealSummary().then(setSummary).catch(() => setSummary(null)),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => {
    refresh()
    const iv = setInterval(refresh, 15000)
    return () => clearInterval(iv)
  }, [])

  const filtered = useMemo(() => {
    let list = deals
    if (filter === 'high-risk') list = list.filter(d => d.overall_risk_score > 0.6)
    else if (filter === 'processing') list = list.filter(d => d.status === 'processing' || d.status === 'pending')
    else if (filter === 'completed') list = list.filter(d => d.status === 'completed')
    const q = query.trim().toLowerCase()
    if (q) list = list.filter(d =>
      d.title.toLowerCase().includes(q) ||
      d.job_id.toLowerCase().includes(q) ||
      (d.top_topic ?? '').toLowerCase().includes(q) ||
      (d.top_objection ?? '').toLowerCase().includes(q),
    )
    return list
  }, [deals, filter, query])

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Inbox className="w-4 h-4 text-indigo-600" />
            </div>
            <h1 className="page-title">Deal Inbox</h1>
          </div>
          <p className="page-subtitle">Every processed call as a deal row, ranked by risk.</p>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:border-slate-300 text-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Tile label="Total deals" value={summary?.total ?? 0} />
        <Tile label="High-risk" value={summary?.high_risk_deals ?? 0} accent={(summary?.high_risk_deals ?? 0) > 0 ? 'red' : undefined} />
        <Tile label="Processing" value={summary?.processing ?? 0} accent={(summary?.processing ?? 0) > 0 ? 'indigo' : undefined} />
        <Tile label="Avg risk" value={`${Math.round((summary?.avg_risk ?? 0) * 100)}%`} />
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex bg-slate-100 rounded-xl p-1 gap-1">
          {([
            ['all', 'All'],
            ['high-risk', 'High-risk'],
            ['processing', 'Processing'],
            ['completed', 'Completed'],
          ] as const).map(([v, label]) => (
            <button
              key={v}
              onClick={() => setFilter(v)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                filter === v ? 'bg-white text-slate-900 shadow' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-md">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            type="search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Filter by topic, objection, company…"
            className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
        <Link to="/upload" className="ml-auto btn-primary !py-2 !px-4 !text-xs">+ New deal</Link>
      </div>

      {/* Deal grid */}
      {filtered.length === 0 ? (
        <div className="card p-10 text-center">
          <Inbox className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">No deals match this filter.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(d => (
            <Link
              key={d.job_id}
              to={`/results/${d.job_id}`}
              className="group block rounded-2xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-md transition-all overflow-hidden"
            >
              <div className="flex items-center gap-4 p-4">
                <StatusBadge status={d.status} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-slate-800 truncate">{d.title}</p>
                    <span className="font-mono text-[10px] text-slate-400">{d.job_id.slice(0, 8)}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500">
                    {d.top_topic && <span className="capitalize">{d.top_topic}</span>}
                    {d.top_objection && (
                      <>
                        <span className="text-slate-300">·</span>
                        <span className="flex items-center gap-1 text-amber-600">
                          <AlertTriangle className="w-3 h-3" />{d.top_objection.slice(0, 40)}
                        </span>
                      </>
                    )}
                    <span className="text-slate-300">·</span>
                    <span>{d.segment_count} segments</span>
                    {d.high_risk_count > 0 && (
                      <>
                        <span className="text-slate-300">·</span>
                        <span className="text-red-600 font-semibold">{d.high_risk_count} high-risk</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="w-40">
                  <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                    <span>Risk</span>
                    <span className="tabular-nums font-mono text-slate-700">{Math.round(d.overall_risk_score * 100)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full bg-gradient-to-r ${riskColor(d.overall_risk_score)} transition-all`}
                      style={{ width: `${Math.round(d.overall_risk_score * 100)}%` }}
                    />
                  </div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-500 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function Tile({ label, value, accent }: { label: string; value: string | number; accent?: 'red' | 'indigo' }) {
  const cls = accent === 'red' ? 'text-red-600' : accent === 'indigo' ? 'text-indigo-600' : 'text-slate-900'
  return (
    <div className="card p-4">
      <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 tabular-nums ${cls}`}>{value}</p>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'completed') return (
    <span className="w-8 h-8 flex items-center justify-center rounded-xl bg-emerald-50 text-emerald-600"><CheckCircle2 className="w-4 h-4" /></span>
  )
  if (status === 'failed') return (
    <span className="w-8 h-8 flex items-center justify-center rounded-xl bg-red-50 text-red-500"><XCircle className="w-4 h-4" /></span>
  )
  return (
    <span className="w-8 h-8 flex items-center justify-center rounded-xl bg-indigo-50 text-indigo-500">
      <Loader2 className="w-4 h-4 animate-spin" />
    </span>
  )
}
