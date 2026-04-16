import { useEffect, useState } from 'react'
import { Zap, RefreshCw, TrendingUp, CheckCircle2, XCircle, Rewind, Rocket, AlertCircle, Loader2 } from 'lucide-react'
import {
  getFlywheelStatus, listCorrections, listAdapters,
  trainAdapter, promoteAdapter, rollbackAdapter,
  type Adapter, type ExtractionCorrection,
} from '../api/client'

export function Flywheel() {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof getFlywheelStatus>> | null>(null)
  const [corrections, setCorrections] = useState<ExtractionCorrection[]>([])
  const [adapters, setAdapters] = useState<Adapter[]>([])
  const [training, setTraining] = useState(false)
  const [error, setError] = useState('')

  const refresh = () => {
    getFlywheelStatus().then(setStatus).catch(() => {})
    listCorrections(undefined, 100).then(r => setCorrections(r.corrections)).catch(() => {})
    listAdapters().then(r => setAdapters(r.adapters)).catch(() => {})
  }

  useEffect(() => {
    refresh()
    const iv = setInterval(refresh, 10000)
    return () => clearInterval(iv)
  }, [])

  const train = async (dryRun: boolean) => {
    setError('')
    setTraining(true)
    try {
      await trainAdapter(undefined, dryRun)
      refresh()
    } catch (e) { setError((e as Error).message) }
    finally { setTraining(false) }
  }

  const onPromote = async (a: Adapter) => {
    try { await promoteAdapter(a.id); refresh() } catch (e) { setError((e as Error).message) }
  }
  const onRollback = async (a: Adapter) => {
    try { await rollbackAdapter(a.id); refresh() } catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
            <Zap className="w-4 h-4 text-violet-600" />
          </div>
          <h1 className="page-title">Flywheel</h1>
        </div>
        <p className="page-subtitle">
          Corrections from the Results page train better extractors. Eval gate, promote, rollback.
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Top row stats */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-6">
        <StatTile label="Corrections" value={status?.corrections_total ?? 0} sub={`${status?.corrections_unused ?? 0} unused`} />
        <StatTile label="Adapters" value={status?.adapters_total ?? 0} />
        <StatTile label="Active" value={status?.active_adapter?.name ?? '—'} sub={status?.active_adapter ? `delta ${(status.active_adapter.delta ?? 0).toFixed(3)}` : undefined} />
        <div className="card p-4">
          <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Train</p>
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => train(false)}
              disabled={training || (status?.corrections_unused ?? 0) === 0}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-40"
            >
              {training ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
              Train
            </button>
            <button
              onClick={() => train(true)}
              disabled={training || (status?.corrections_unused ?? 0) === 0}
              className="px-3 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm font-semibold hover:bg-slate-200 disabled:opacity-40"
            >
              Dry-run
            </button>
            <button
              onClick={refresh}
              className="px-3 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm hover:bg-slate-200"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Adapters table */}
      <div className="card p-0 overflow-hidden mb-6">
        <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 flex items-center">
          <p className="text-sm font-bold text-slate-700">Adapter registry</p>
          <span className="ml-auto text-xs text-slate-400">{adapters.length} total</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-100">
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-right">Examples</th>
              <th className="px-4 py-2 text-right">Baseline</th>
              <th className="px-4 py-2 text-right">Candidate</th>
              <th className="px-4 py-2 text-right">Δ</th>
              <th className="px-4 py-2 text-center">Status</th>
              <th className="px-4 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {adapters.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400 text-xs">
                No adapters yet — submit corrections from Results and click Train.
              </td></tr>
            )}
            {adapters.map(a => (
              <tr key={a.id} className="border-b border-slate-50 last:border-0">
                <td className="px-4 py-3 font-mono text-xs">{a.name}</td>
                <td className="px-4 py-3 text-right tabular-nums">{a.training_examples}</td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-500">{a.baseline_score?.toFixed(3) ?? '—'}</td>
                <td className="px-4 py-3 text-right tabular-nums font-semibold">{a.candidate_score?.toFixed(3) ?? '—'}</td>
                <td className={`px-4 py-3 text-right tabular-nums font-semibold ${
                  (a.delta ?? 0) > 0 ? 'text-emerald-600' : (a.delta ?? 0) < 0 ? 'text-red-500' : 'text-slate-500'
                }`}>
                  {a.delta != null ? (a.delta > 0 ? '+' : '') + a.delta.toFixed(3) : '—'}
                </td>
                <td className="px-4 py-3 text-center">
                  {a.promoted
                    ? <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full"><CheckCircle2 className="w-3 h-3" />Active</span>
                    : <span className="text-xs text-slate-400">candidate</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  {!a.promoted ? (
                    <button onClick={() => onPromote(a)} className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">
                      Promote →
                    </button>
                  ) : (
                    <button onClick={() => onRollback(a)} className="text-xs font-semibold text-red-500 hover:text-red-700 inline-flex items-center gap-1">
                      <Rewind className="w-3 h-3" />Rollback
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent corrections */}
      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 flex items-center">
          <p className="text-sm font-bold text-slate-700">Recent corrections</p>
          <span className="ml-auto text-xs text-slate-400">{corrections.length} shown</span>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {corrections.length === 0 && (
            <div className="px-5 py-6 text-center text-slate-400 text-xs">No corrections yet.</div>
          )}
          {corrections.map(c => {
            const orig = c.original_extraction as { topic?: string; risk?: string; risk_score?: number }
            const corr = c.corrected_extraction as { topic?: string; risk?: string; risk_score?: number }
            return (
              <div key={c.id} className="px-5 py-3 border-b border-slate-50 last:border-0">
                <div className="flex items-center gap-3 text-xs">
                  <span className="font-mono text-indigo-600">{c.timestamp_str}</span>
                  <span className="text-slate-400">·</span>
                  <span className="text-slate-500 font-mono">{c.job_id.slice(0, 8)}</span>
                  <span className="text-slate-400">·</span>
                  <span className="capitalize text-slate-600">{orig.topic} → <strong className="text-indigo-700">{corr.topic}</strong></span>
                  <span className="text-slate-400">·</span>
                  <span className="text-slate-600">risk {orig.risk} → <strong className="text-indigo-700">{corr.risk}</strong></span>
                  {c.used_for_training && (
                    <span className="ml-auto inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600">
                      <CheckCircle2 className="w-3 h-3" />trained
                    </span>
                  )}
                </div>
                {c.notes && <p className="mt-1 text-xs text-slate-500 italic">"{c.notes}"</p>}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function StatTile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card p-4">
      <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">{label}</p>
      <p className="text-2xl font-bold mt-1 tabular-nums">{value}</p>
      {sub && <p className="text-[11px] text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}
