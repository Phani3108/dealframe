import { useEffect, useState } from 'react'
import { Layers, ShoppingCart, Briefcase, Heart, Home, Users, Sparkles, AlertTriangle, Target, TrendingUp } from 'lucide-react'
import { listVerticalPacks, getVerticalDashboard, type VerticalPackSummary, type VerticalDashboard } from '../api/client'

const PACK_ICONS: Record<string, typeof Layers> = {
  sales: Briefcase,
  procurement: ShoppingCart,
  customer_success: Heart,
  real_estate: Home,
  ux_research: Users,
}

const PACK_GRADIENT: Record<string, string> = {
  sales: 'from-indigo-500 to-violet-600',
  procurement: 'from-emerald-500 to-teal-600',
  customer_success: 'from-rose-500 to-pink-600',
  real_estate: 'from-amber-500 to-orange-600',
  ux_research: 'from-sky-500 to-cyan-600',
}

export function Verticals() {
  const [packs, setPacks] = useState<VerticalPackSummary[]>([])
  const [selected, setSelected] = useState<VerticalPackSummary | null>(null)
  const [dashboard, setDashboard] = useState<VerticalDashboard | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listVerticalPacks()
      .then(r => {
        setPacks(r.packs)
        if (r.packs[0]) setSelected(r.packs[0])
      })
      .catch(() => setPacks([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selected) return
    getVerticalDashboard(selected.id)
      .then(setDashboard)
      .catch(() => setDashboard(null))
  }, [selected])

  const Icon = selected ? (PACK_ICONS[selected.id] ?? Layers) : Layers
  const gradient = selected ? (PACK_GRADIENT[selected.id] ?? 'from-slate-500 to-slate-600') : 'from-slate-500 to-slate-600'

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
            <Layers className="w-4 h-4 text-violet-600" />
          </div>
          <h1 className="page-title">Vertical Packs</h1>
        </div>
        <p className="page-subtitle">Domain-tuned schemas, extraction prompts, and dashboards per industry.</p>
      </div>

      {loading ? (
        <p className="text-center py-10 text-sm text-slate-400">Loading packs…</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
          {/* Left: pack list */}
          <div className="space-y-2">
            {packs.map(p => {
              const PIcon = PACK_ICONS[p.id] ?? Layers
              const active = selected?.id === p.id
              return (
                <button
                  key={p.id}
                  onClick={() => setSelected(p)}
                  className={`w-full flex items-center gap-3 rounded-2xl border p-3 text-left transition ${
                    active ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br ${PACK_GRADIENT[p.id] ?? 'from-slate-500 to-slate-600'}`}>
                    <PIcon className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-800">{p.name}</p>
                    <p className="text-[10px] text-slate-500 truncate">{p.field_count} fields · {p.industries.length} industries</p>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Right: pack detail + dashboard */}
          {selected && (
            <div className="space-y-5">
              <div className={`rounded-2xl bg-gradient-to-br ${gradient} p-6 text-white shadow-lg shadow-slate-900/10`}>
                <div className="flex items-center gap-3 mb-2">
                  <Icon className="w-5 h-5" />
                  <h2 className="text-xl font-bold">{selected.name}</h2>
                </div>
                <p className="text-sm opacity-90 mb-3">{selected.description}</p>
                <div className="flex flex-wrap gap-2">
                  {selected.industries.map(ind => (
                    <span key={ind} className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-white/20">
                      {ind}
                    </span>
                  ))}
                </div>
              </div>

              {/* Prompt hint */}
              {selected.prompt_hint && (
                <div className="card p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                    <h3 className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Pack-specific extraction prompt</h3>
                  </div>
                  <p className="text-sm text-slate-700 leading-relaxed">{selected.prompt_hint}</p>
                </div>
              )}

              {/* Dashboard stats */}
              {dashboard && (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Tile label="Deals" value={dashboard.deal_count} />
                    <Tile label="Segments" value={dashboard.total_segments ?? 0} />
                    <Tile label="Avg risk" value={`${Math.round(dashboard.avg_risk * 100)}%`} />
                    <Tile label="High-risk rate" value={`${Math.round(dashboard.high_risk_rate * 100)}%`} accent={dashboard.high_risk_rate > 0.3 ? 'red' : undefined} />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <BarList title="Top topics" icon={Target} rows={dashboard.top_topics} emptyLabel="No topics yet." />
                    <BarList title="Top objections" icon={AlertTriangle} rows={dashboard.top_objections} emptyLabel="No objections yet." />
                    <BarList title="Pack-specific hits" icon={TrendingUp} rows={dashboard.pack_field_hits ?? []} emptyLabel="No pack-specific signals yet." />
                  </div>
                </>
              )}

              {/* Schema fields */}
              <div className="card p-4">
                <h3 className="text-[10px] uppercase tracking-wider font-bold text-slate-500 mb-2">Schema fields</h3>
                <div className="flex flex-wrap gap-1.5">
                  {selected.fields.map(f => (
                    <span key={f.name} className="text-[11px] font-mono px-2 py-1 rounded bg-slate-100 text-slate-700">
                      {f.name} <span className="text-slate-400">{f.type.toLowerCase()}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Tile({ label, value, accent }: { label: string; value: string | number; accent?: 'red' }) {
  const cls = accent === 'red' ? 'text-red-600' : 'text-slate-900'
  return (
    <div className="card p-4">
      <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 tabular-nums ${cls}`}>{value}</p>
    </div>
  )
}

function BarList({ title, icon: Icon, rows, emptyLabel }: { title: string; icon: typeof Target; rows: Array<[string, number]>; emptyLabel: string }) {
  const max = rows.reduce((m, [, c]) => Math.max(m, c), 0) || 1
  return (
    <div className="card p-4">
      <div className="flex items-center gap-1.5 mb-3">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
        <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">{title}</p>
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400 italic">{emptyLabel}</p>
      ) : (
        <ul className="space-y-1.5">
          {rows.map(([k, c]) => (
            <li key={k} className="text-xs">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-slate-700 truncate">{k}</span>
                <span className="tabular-nums font-mono text-slate-500">{c}</span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-gradient-to-r from-indigo-400 to-violet-500" style={{ width: `${Math.round((c / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
