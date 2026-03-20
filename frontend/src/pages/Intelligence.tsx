import { useState, useEffect } from 'react'
import { RefreshCw, BarChart3 } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from 'recharts'
import { getObjections, getTopicTrends, getRiskSummary } from '../api/client'

const RISK_COLORS = ['#EF4444', '#F59E0B', '#10B981']
const TOPIC_COLORS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#06B6D4']

export function Intelligence() {
  const [objections, setObjections] = useState<Array<{ text: string; count: number; risk_avg: number }>>([])
  const [riskSummary, setRiskSummary] = useState<{ high: number; medium: number; low: number; average_score: number } | null>(null)
  const [topicTrends, setTopicTrends] = useState<Array<{ topic: string; daily_counts: Record<string, number> }>>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.allSettled([
      getObjections(10).then(r => setObjections(r.objections ?? [])).catch(() => {}),
      getRiskSummary().then(setRiskSummary).catch(() => {}),
      getTopicTrends().then(r => setTopicTrends(r.topics ?? [])).catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const objData = objections.map(o => ({ name: o.text.slice(0, 30), count: o.count, risk: Number((o.risk_avg * 100).toFixed(0)) }))

  const riskPieData = riskSummary
    ? [
        { name: 'High', value: riskSummary.high },
        { name: 'Medium', value: riskSummary.medium },
        { name: 'Low', value: riskSummary.low },
      ].filter(d => d.value > 0)
    : []

  // Build trend line data — collect all dates, create one entry per date
  const allDates = [...new Set(
    topicTrends.flatMap(t => Object.keys(t.daily_counts))
  )].sort()

  const trendData = allDates.map(date => {
    const entry: Record<string, string | number> = { date: date.slice(5) } // MM-DD
    topicTrends.forEach(t => {
      entry[t.topic] = t.daily_counts[date] ?? 0
    })
    return entry
  })

  const isEmpty = objections.length === 0 && !riskSummary

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">Intelligence</h1>
          <p className="page-subtitle">Cross-video patterns, trends, and risk analytics</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-1.5">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {isEmpty && !loading ? (
        <div className="card p-16 text-center">
          <BarChart3 className="w-12 h-12 text-slate-200 mx-auto mb-3" />
          <p className="text-slate-500 font-medium">No intelligence data yet</p>
          <p className="text-sm text-slate-400 mt-1">Process videos to see cross-video patterns.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Top objections + Risk pie */}
          <div className="grid grid-cols-3 gap-6">
            {/* Objections bar chart */}
            <div className="col-span-2 card p-5">
              <h2 className="text-sm font-semibold text-slate-900 mb-5">Top Objections</h2>
              {objData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-slate-300 text-sm">
                  No objections recorded
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={objData} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 11, fill: '#475569' }}
                      axisLine={false}
                      tickLine={false}
                      width={160}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #E2E8F0' }}
                      cursor={{ fill: '#F8FAFC' }}
                    />
                    <Bar dataKey="count" fill="#6366F1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Risk distribution pie */}
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-slate-900 mb-0">Risk Distribution</h2>
              {riskPieData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-slate-300 text-sm mt-4">
                  No risk data
                </div>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie
                        data={riskPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={75}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {riskPieData.map((_, index) => (
                          <Cell key={index} fill={RISK_COLORS[index]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex justify-center gap-4 mt-1">
                    {riskPieData.map((d, i) => (
                      <div key={d.name} className="flex items-center gap-1.5 text-xs text-slate-600">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: RISK_COLORS[i] }} />
                        {d.name} ({d.value})
                      </div>
                    ))}
                  </div>
                  {riskSummary && (
                    <p className="text-center text-xs text-slate-400 mt-2">
                      Avg risk: <span className="font-semibold text-slate-600">{(riskSummary.average_score * 100).toFixed(0)}%</span>
                    </p>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Topic trends */}
          {trendData.length > 0 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-slate-900 mb-5">Topic Trends Over Time</h2>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trendData} margin={{ left: 0, right: 16 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {topicTrends.map((t, i) => (
                    <Line
                      key={t.topic}
                      type="monotone"
                      dataKey={t.topic}
                      stroke={TOPIC_COLORS[i % TOPIC_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Objections detail table */}
          {objections.length > 0 && (
            <div className="card">
              <div className="px-5 py-4 border-b border-slate-100">
                <h2 className="text-sm font-semibold text-slate-900">Objection Detail</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 font-medium uppercase tracking-wide border-b border-slate-100">
                      <th className="text-left px-5 py-3">Objection</th>
                      <th className="text-right px-5 py-3">Count</th>
                      <th className="text-right px-5 py-3">Avg Risk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {objections.map((obj, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3 text-slate-700">{obj.text}</td>
                        <td className="px-5 py-3 text-right text-slate-600 tabular-nums font-medium">×{obj.count}</td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          <span className={`font-semibold ${
                            obj.risk_avg > 0.6 ? 'text-red-600' : obj.risk_avg > 0.3 ? 'text-amber-600' : 'text-emerald-600'
                          }`}>
                            {(obj.risk_avg * 100).toFixed(0)}%
                          </span>
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
  )
}
