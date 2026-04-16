import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Activity, ShieldCheck, AlertTriangle, Loader2 } from 'lucide-react'
import { getSharedDeal, type SegmentPair } from '../api/client'
import { DealTimeline } from '../components/DealTimeline'
import { SegmentCard } from '../components/SegmentCard'

export function SharedDeal() {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<Awaited<ReturnType<typeof getSharedDeal>> | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    getSharedDeal(token)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) {
    return <div className="p-10 text-center text-slate-400 flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading shared deal…</div>
  }

  if (error || !data) {
    return (
      <div className="p-10 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-slate-600 font-medium">{error || 'Link not found.'}</p>
        <p className="text-xs text-slate-400 mt-1">This share link may be expired or revoked.</p>
      </div>
    )
  }

  const intel = data.result as unknown as { segments?: SegmentPair[]; overall_risk_score?: number; duration_ms?: number }
  const segments: SegmentPair[] = intel.segments ?? []

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <Activity className="w-5 h-5 text-indigo-500" />
          <p className="font-bold text-slate-800">DealFrame</p>
          <span className="text-slate-300">·</span>
          <p className="text-sm text-slate-600">{data.title}</p>
          <span className="ml-auto flex items-center gap-1 text-xs text-emerald-600">
            <ShieldCheck className="w-3.5 h-3.5" />Read-only share
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="card p-5 flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Overall risk</p>
            <p className="text-4xl font-bold tabular-nums text-slate-900">
              {Math.round((intel.overall_risk_score ?? 0) * 100)}%
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Segments</p>
            <p className="text-3xl font-bold tabular-nums text-slate-900">{segments.length}</p>
          </div>
        </div>

        {segments.length > 0 && (
          <DealTimeline segments={segments} durationMs={intel.duration_ms} />
        )}

        <div className="space-y-3">
          {segments.map((pair, i) => (
            <SegmentCard key={i} pair={pair} />
          ))}
        </div>

        <p className="text-center text-xs text-slate-400 pt-8">
          Powered by DealFrame · Video → Negotiation Intelligence
        </p>
      </main>
    </div>
  )
}
