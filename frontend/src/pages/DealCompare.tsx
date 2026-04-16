import { useEffect, useMemo, useState } from 'react'
import { ArrowLeftRight, GitCompare, AlertTriangle, Target, Sparkles, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { listJobs, getJob, type Job, type SegmentPair } from '../api/client'

interface DealStats {
  job_id: string
  title: string
  segments: SegmentPair[]
  overallRisk: number
  highRiskCount: number
  avgRisk: number
  topics: Map<string, number>
  objections: Map<string, number>
  decisionSignals: number
  sentimentBreakdown: { positive: number; negative: number; neutral: number }
}

function summarize(job: Job): DealStats {
  const segments: SegmentPair[] = (job.result?.segments ?? []) as SegmentPair[]
  const topics = new Map<string, number>()
  const objections = new Map<string, number>()
  let highRiskCount = 0
  let riskSum = 0
  let decisionSignals = 0
  const sentimentBreakdown = { positive: 0, negative: 0, neutral: 0 }

  for (const p of segments) {
    const e = p.extraction
    if (e.topic) topics.set(e.topic, (topics.get(e.topic) ?? 0) + 1)
    if (e.risk_score != null) {
      riskSum += e.risk_score
      if (e.risk_score > 0.6) highRiskCount += 1
    }
    for (const o of e.objections ?? []) {
      const k = o.toLowerCase().slice(0, 60)
      objections.set(k, (objections.get(k) ?? 0) + 1)
    }
    decisionSignals += (e.decision_signals ?? []).length
    const sent = (e.sentiment ?? 'neutral').toLowerCase()
    if (sent.startsWith('pos')) sentimentBreakdown.positive += 1
    else if (sent.startsWith('neg')) sentimentBreakdown.negative += 1
    else sentimentBreakdown.neutral += 1
  }

  return {
    job_id: job.job_id,
    title: job.job_id.slice(0, 10),
    segments,
    overallRisk: job.result?.overall_risk_score ?? 0,
    highRiskCount,
    avgRisk: segments.length ? riskSum / segments.length : 0,
    topics,
    objections,
    decisionSignals,
    sentimentBreakdown,
  }
}

function topN(map: Map<string, number>, n = 5): Array<[string, number]> {
  return Array.from(map.entries()).sort((a, b) => b[1] - a[1]).slice(0, n)
}

function delta(a: number, b: number): { sign: number; pct: number } {
  if (a === 0 && b === 0) return { sign: 0, pct: 0 }
  const d = b - a
  const base = Math.max(Math.abs(a), Math.abs(b))
  return { sign: Math.sign(d), pct: base ? Math.abs(d) / base : 0 }
}

function DeltaBadge({ a, b, invert = false }: { a: number; b: number; invert?: boolean }) {
  const d = delta(a, b)
  if (d.sign === 0) return <Minus className="w-3 h-3 text-slate-400" />
  const good = invert ? d.sign < 0 : d.sign > 0
  const cls = good ? 'text-emerald-600 bg-emerald-50' : 'text-red-600 bg-red-50'
  const Icon = d.sign > 0 ? TrendingUp : TrendingDown
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono ${cls}`}>
      <Icon className="w-2.5 h-2.5" />
      {Math.round(d.pct * 100)}%
    </span>
  )
}

export function DealCompare() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobA, setJobA] = useState('')
  const [jobB, setJobB] = useState('')
  const [statsA, setStatsA] = useState<DealStats | null>(null)
  const [statsB, setStatsB] = useState<DealStats | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    listJobs().then(r => {
      const completed = (r?.jobs ?? []).filter(j => j.status === 'completed')
      setJobs(completed)
      if (completed.length >= 2) {
        setJobA(completed[0].job_id)
        setJobB(completed[1].job_id)
      }
    }).catch(() => setJobs([]))
  }, [])

  const run = async () => {
    if (!jobA || !jobB || jobA === jobB) return
    setLoading(true)
    try {
      const [a, b] = await Promise.all([getJob(jobA), getJob(jobB)])
      setStatsA(summarize(a))
      setStatsB(summarize(b))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (jobA && jobB && jobA !== jobB) run() }, [jobA, jobB])  // eslint-disable-line react-hooks/exhaustive-deps

  const sharedTopics = useMemo(() => {
    if (!statsA || !statsB) return [] as string[]
    const set = new Set<string>()
    statsA.topics.forEach((_, k) => { if (statsB.topics.has(k)) set.add(k) })
    return Array.from(set)
  }, [statsA, statsB])

  const divergentTopics = useMemo(() => {
    if (!statsA || !statsB) return { onlyA: [] as string[], onlyB: [] as string[] }
    const onlyA = Array.from(statsA.topics.keys()).filter(k => !statsB.topics.has(k))
    const onlyB = Array.from(statsB.topics.keys()).filter(k => !statsA.topics.has(k))
    return { onlyA, onlyB }
  }, [statsA, statsB])

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
            <ArrowLeftRight className="w-4 h-4 text-violet-600" />
          </div>
          <h1 className="page-title">Deal Compare</h1>
        </div>
        <p className="page-subtitle">Side-by-side negotiation intelligence for any two deals.</p>
      </div>

      {/* Selectors */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <select
          value={jobA}
          onChange={e => setJobA(e.target.value)}
          className="px-3 py-2 rounded-xl border border-slate-200 text-sm bg-white min-w-[220px]"
        >
          <option value="">Select deal A…</option>
          {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.job_id.slice(0, 10)}…</option>)}
        </select>
        <ArrowLeftRight className="w-4 h-4 text-slate-300" />
        <select
          value={jobB}
          onChange={e => setJobB(e.target.value)}
          className="px-3 py-2 rounded-xl border border-slate-200 text-sm bg-white min-w-[220px]"
        >
          <option value="">Select deal B…</option>
          {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.job_id.slice(0, 10)}…</option>)}
        </select>
        <button
          onClick={run}
          disabled={!jobA || !jobB || jobA === jobB || loading}
          className="btn-primary !py-2 !px-4 !text-xs flex items-center gap-1.5"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <GitCompare className="w-3.5 h-3.5" />}
          {loading ? 'Loading…' : 'Compare'}
        </button>
      </div>

      {!statsA || !statsB ? (
        <div className="card p-12 text-center">
          <GitCompare className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">Select two completed deals to see a side-by-side comparison.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Header rows */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <DealCard stats={statsA} />
            <DealCard stats={statsB} />
          </div>

          {/* Side-by-side metric deltas */}
          <div className="card p-5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">Key metrics</h3>
            <MetricRow label="Overall risk" a={statsA.overallRisk * 100} b={statsB.overallRisk * 100} unit="%" invert />
            <MetricRow label="High-risk segments" a={statsA.highRiskCount} b={statsB.highRiskCount} invert />
            <MetricRow label="Avg risk" a={statsA.avgRisk * 100} b={statsB.avgRisk * 100} unit="%" invert />
            <MetricRow label="Decision signals" a={statsA.decisionSignals} b={statsB.decisionSignals} />
            <MetricRow label="Total segments" a={statsA.segments.length} b={statsB.segments.length} />
            <MetricRow label="Positive sentiment" a={statsA.sentimentBreakdown.positive} b={statsB.sentimentBreakdown.positive} />
            <MetricRow label="Negative sentiment" a={statsA.sentimentBreakdown.negative} b={statsB.sentimentBreakdown.negative} invert />
          </div>

          {/* Topic diffs */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ListCard title="Only in Deal A" icon={Target} items={divergentTopics.onlyA.slice(0, 8)} emptyLabel="(no unique topics)" />
            <ListCard title="In both deals" icon={Sparkles} items={sharedTopics.slice(0, 8)} emptyLabel="(no shared topics)" />
            <ListCard title="Only in Deal B" icon={Target} items={divergentTopics.onlyB.slice(0, 8)} emptyLabel="(no unique topics)" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ObjectionsCard title={`Top objections — Deal A (${statsA.job_id.slice(0, 8)})`} entries={topN(statsA.objections)} />
            <ObjectionsCard title={`Top objections — Deal B (${statsB.job_id.slice(0, 8)})`} entries={topN(statsB.objections)} />
          </div>
        </div>
      )}
    </div>
  )
}

function DealCard({ stats }: { stats: DealStats }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Deal</p>
        <span className="font-mono text-[10px] text-slate-400">{stats.job_id.slice(0, 10)}</span>
      </div>
      <div className="flex items-end gap-6 mb-4">
        <div>
          <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Risk</p>
          <p className="text-3xl font-bold tabular-nums text-slate-900">{Math.round(stats.overallRisk * 100)}%</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Segments</p>
          <p className="text-3xl font-bold tabular-nums text-slate-900">{stats.segments.length}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">High-risk</p>
          <p className={`text-3xl font-bold tabular-nums ${stats.highRiskCount > 0 ? 'text-red-600' : 'text-slate-900'}`}>
            {stats.highRiskCount}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {topN(stats.topics, 4).map(([t, c]) => (
          <span key={t} className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600">
            {t} · {c}
          </span>
        ))}
      </div>
    </div>
  )
}

function MetricRow({ label, a, b, unit = '', invert = false }: { label: string; a: number; b: number; unit?: string; invert?: boolean }) {
  return (
    <div className="flex items-center py-2 border-b border-slate-100 last:border-b-0">
      <span className="text-xs text-slate-500 flex-1">{label}</span>
      <span className="tabular-nums font-mono text-sm text-slate-800 w-24 text-right">{a.toFixed(unit === '%' ? 0 : 0)}{unit}</span>
      <div className="w-12 flex justify-center"><DeltaBadge a={a} b={b} invert={invert} /></div>
      <span className="tabular-nums font-mono text-sm text-slate-800 w-24 text-right">{b.toFixed(unit === '%' ? 0 : 0)}{unit}</span>
    </div>
  )
}

function ListCard({ title, icon: Icon, items, emptyLabel }: { title: string; icon: typeof Target; items: string[]; emptyLabel: string }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
        <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">{title}</p>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-slate-400 italic">{emptyLabel}</p>
      ) : (
        <ul className="space-y-1">
          {items.map(t => <li key={t} className="text-sm text-slate-700 capitalize">· {t}</li>)}
        </ul>
      )}
    </div>
  )
}

function ObjectionsCard({ title, entries }: { title: string; entries: Array<[string, number]> }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-1.5 mb-3">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
        <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">{title}</p>
      </div>
      {entries.length === 0 ? (
        <p className="text-xs text-slate-400 italic">No objections detected.</p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map(([t, c]) => (
            <li key={t} className="flex items-center gap-2 text-xs">
              <span className="tabular-nums font-mono text-slate-500 w-6 text-right">{c}</span>
              <span className="text-slate-700 flex-1 truncate">{t}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
