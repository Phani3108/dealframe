import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Shield, Activity, Filter, Clock, User, Database, Download,
  Search, CalendarRange, RefreshCw, ChevronLeft, ChevronRight,
} from 'lucide-react'
import {
  queryAudit, getAuditStats, auditExportUrl,
  type AuditEntry, type AuditQueryParams,
} from '../api/client'

const PAGE_SIZES = [25, 50, 100, 200] as const

function toEpochSeconds(iso: string): number | undefined {
  if (!iso) return undefined
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? undefined : Math.floor(t / 1000)
}

function toInputDate(epochSec: number | undefined): string {
  if (!epochSec) return ''
  const d = new Date(epochSec * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [stats, setStats] = useState<{ total_entries: number; action_counts: Record<string, number>; resource_counts: Record<string, number> } | null>(null)

  const [filterAction, setFilterAction] = useState('')
  const [filterResource, setFilterResource] = useState('')
  const [filterUser, setFilterUser] = useState('')
  const [search, setSearch] = useState('')
  const [sinceIso, setSinceIso] = useState('')
  const [untilIso, setUntilIso] = useState('')

  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState<number>(50)
  const [total, setTotal] = useState(0)

  const filters: AuditQueryParams = useMemo(() => ({
    action: filterAction || undefined,
    resource_type: filterResource || undefined,
    user_id: filterUser || undefined,
    q: search || undefined,
    since: toEpochSeconds(sinceIso),
    until: toEpochSeconds(untilIso),
    limit,
    offset: page * limit,
  }), [filterAction, filterResource, filterUser, search, sinceIso, untilIso, limit, page])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [res, st] = await Promise.all([
        queryAudit(filters),
        getAuditStats(),
      ])
      setEntries(res.entries ?? [])
      setTotal(res.total ?? 0)
      setStats(st)
    } catch { /* ignore */ }
    setLoading(false)
  }, [filters])

  useEffect(() => { void load() }, [load])

  const resetFilters = () => {
    setFilterAction('')
    setFilterResource('')
    setFilterUser('')
    setSearch('')
    setSinceIso('')
    setUntilIso('')
    setPage(0)
  }

  const totalPages = Math.max(1, Math.ceil(total / limit))
  const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleString()

  const actionBadge: Record<string, string> = {
    create: 'bg-emerald-100 text-emerald-700',
    update: 'bg-blue-100 text-blue-700',
    delete: 'bg-red-100 text-red-700',
    export: 'bg-orange-100 text-orange-700',
    login: 'bg-yellow-100 text-yellow-700',
    logout: 'bg-slate-100 text-slate-600',
    read: 'bg-violet-100 text-violet-700',
  }

  const exportHref = (fmt: 'csv' | 'json') => auditExportUrl({ ...filters, limit: undefined, offset: undefined, fmt })

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in">
      <div className="relative mb-8 bg-gradient-to-br from-violet-600 via-violet-700 to-purple-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-violet-900/20">
        <div className="relative flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-violet-300 animate-pulse" />
              <span className="text-xs font-semibold text-violet-200 uppercase tracking-widest">Security</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Audit Log</h1>
            <p className="text-violet-200 text-sm mt-1">Complete activity trail across the platform</p>
          </div>
          <div className="flex items-center gap-2">
            <a href={exportHref('csv')} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm transition border border-white/10">
              <Download className="w-4 h-4" />CSV
            </a>
            <a href={exportHref('json')} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm transition border border-white/10">
              <Download className="w-4 h-4" />JSON
            </a>
            <button onClick={() => void load()} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm transition border border-white/10">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />Refresh
            </button>
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Activity className="w-4 h-4 text-violet-600" /><span className="text-xs text-slate-500 font-medium">Total Events</span></div>
            <p className="text-xl font-bold text-slate-700">{stats.total_entries}</p>
          </div>
          {Object.entries(stats.action_counts).slice(0, 3).map(([k, v]) => (
            <div key={k} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-1"><span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${actionBadge[k] ?? 'bg-slate-100 text-slate-600'}`}>{k}</span></div>
              <p className="text-xl font-bold text-slate-700">{v}</p>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-6">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          <Filter className="w-3.5 h-3.5" /> Filters
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Action
            <input value={filterAction} onChange={e => { setFilterAction(e.target.value); setPage(0) }} placeholder="create / update / delete…" className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Resource
            <input value={filterResource} onChange={e => { setFilterResource(e.target.value); setPage(0) }} placeholder="video / export / settings…" className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            User
            <input value={filterUser} onChange={e => { setFilterUser(e.target.value); setPage(0) }} placeholder="user id / email…" className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Search
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} placeholder="full-text" className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm" />
            </div>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            <span className="flex items-center gap-1"><CalendarRange className="w-3.5 h-3.5" /> From</span>
            <input type="datetime-local" value={sinceIso} onChange={e => { setSinceIso(e.target.value); setPage(0) }} className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            <span className="flex items-center gap-1"><CalendarRange className="w-3.5 h-3.5" /> To</span>
            <input type="datetime-local" value={untilIso} onChange={e => { setUntilIso(e.target.value); setPage(0) }} className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            Page size
            <select value={limit} onChange={e => { setLimit(Number(e.target.value)); setPage(0) }} className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm shadow-sm">
              {PAGE_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <button onClick={resetFilters} className="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition">Reset filters</button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400">Quick range:</span>
          {[
            { label: 'Last hour', sec: 3600 },
            { label: 'Last 24h', sec: 24 * 3600 },
            { label: 'Last 7d', sec: 7 * 24 * 3600 },
            { label: 'Last 30d', sec: 30 * 24 * 3600 },
          ].map(q => (
            <button
              key={q.label}
              onClick={() => {
                const now = Math.floor(Date.now() / 1000)
                setUntilIso(toInputDate(now))
                setSinceIso(toInputDate(now - q.sec))
                setPage(0)
              }}
              className="px-2 py-1 rounded-md text-[11px] bg-slate-100 text-slate-600 hover:bg-slate-200 transition"
            >
              {q.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-center py-16 text-slate-400 text-sm">Loading audit trail…</p>
      ) : entries.length === 0 ? (
        <div className="text-center py-16">
          <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No audit entries match the current filters.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Time</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Action</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Resource</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">User</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">IP</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map(e => (
                <tr key={e.id} className="hover:bg-slate-50/50 transition">
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap"><Clock className="w-3 h-3 inline mr-1" />{fmtTime(e.timestamp)}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs font-semibold ${actionBadge[e.action] ?? 'bg-slate-100 text-slate-600'}`}>{e.action || '—'}</span></td>
                  <td className="px-4 py-3 text-xs text-slate-600"><Database className="w-3 h-3 inline mr-1" />{e.resource_type || '—'}{e.resource_id ? ` / ${e.resource_id.slice(0, 12)}${e.resource_id.length > 12 ? '…' : ''}` : ''}</td>
                  <td className="px-4 py-3 text-xs text-slate-600"><User className="w-3 h-3 inline mr-1" />{e.user_id || '—'}</td>
                  <td className="px-4 py-3 text-xs text-slate-400 font-mono">{e.ip_address || '—'}</td>
                  <td className="px-4 py-3 text-xs text-slate-400 max-w-[260px] truncate" title={JSON.stringify(e.details)}>{JSON.stringify(e.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 mt-6">
        <p className="text-xs text-slate-500">
          {total === 0 ? 'No results' : `Showing ${page * limit + 1}–${Math.min(total, (page + 1) * limit)} of ${total}`}
        </p>
        <div className="flex items-center gap-2">
          <button onClick={() => setPage(0)} disabled={page === 0} className="px-2 py-1 text-xs rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition">First</button>
          <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="inline-flex items-center gap-1 px-3 py-1 text-sm rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition">
            <ChevronLeft className="w-3.5 h-3.5" /> Prev
          </button>
          <span className="text-sm text-slate-500">Page {page + 1} / {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page + 1 >= totalPages} className="inline-flex items-center gap-1 px-3 py-1 text-sm rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition">
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setPage(totalPages - 1)} disabled={page + 1 >= totalPages} className="px-2 py-1 text-xs rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition">Last</button>
        </div>
      </div>
    </div>
  )
}
