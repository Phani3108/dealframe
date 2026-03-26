import { useState } from 'react'
import { ChevronDown, ChevronUp, Clock, Swords, Scale, TrendingUp, AlertTriangle } from 'lucide-react'
import { RiskBadge, Badge } from './Badge'
import type { SegmentPair } from '../api/client'

export function msToTimestamp(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

const riskStyles: Record<string, string> = {
  high: 'border-l-red-500 bg-red-50/40',
  medium: 'border-l-amber-400 bg-amber-50/40',
  low: 'border-l-emerald-500 bg-emerald-50/20',
}

export function SegmentCard({ pair }: { pair: SegmentPair }) {
  const [expanded, setExpanded] = useState(false)
  const { segment, extraction } = pair

  return (
    <div
      className={`border border-slate-200 border-l-4 ${riskStyles[extraction.risk] ?? 'border-l-slate-300 bg-white'} rounded-2xl p-4 shadow-sm hover:shadow-md transition-all duration-200`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2.5">
            <span className="inline-flex items-center gap-1 text-xs font-mono text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded-md shadow-sm">
              <Clock className="w-3 h-3" />
              {msToTimestamp(segment.timestamp_ms)}
            </span>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-100 text-xs px-2.5 py-0.5 rounded-full font-semibold capitalize">
              {extraction.topic}
            </span>
            <span className="bg-slate-100 text-slate-600 border border-slate-200 text-xs px-2.5 py-0.5 rounded-full capitalize">
              {extraction.sentiment}
            </span>
            <RiskBadge risk={extraction.risk} />
            <span className="text-xs font-bold text-slate-400 ml-auto tabular-nums">
              {(extraction.risk_score * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-sm text-slate-700 leading-relaxed line-clamp-2">
            {segment.transcript || <em className="text-slate-400">No transcript</em>}
          </p>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0 p-1.5 rounded-lg hover:bg-white/80 transition-colors"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-200/60 space-y-3 animate-fade-in">
          {extraction.objections.length > 0 && (
            <div>
              <p className="text-xs font-bold text-red-600 mb-2 uppercase tracking-wider">
                Objections
              </p>
              <ul className="space-y-1">
                {extraction.objections.map((o, i) => (
                  <li key={i} className="text-xs text-slate-700 flex items-start gap-2 bg-red-50/60 rounded-lg px-3 py-1.5">
                    <span className="text-red-400 mt-0.5 flex-shrink-0">•</span>
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {extraction.decision_signals.length > 0 && (
            <div>
              <p className="text-xs font-bold text-emerald-600 mb-2 uppercase tracking-wider">
                Decision Signals
              </p>
              <ul className="space-y-1">
                {extraction.decision_signals.map((s, i) => (
                  <li key={i} className="text-xs text-slate-700 flex items-start gap-2 bg-emerald-50/60 rounded-lg px-3 py-1.5">
                    <span className="text-emerald-400 mt-0.5 flex-shrink-0">•</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Negotiation Intelligence — only renders if intel fields are present */}
          {(extraction.negotiation_tactics?.length || extraction.power_balance || extraction.bargaining_style) && (
            <div className="bg-violet-50/50 border border-violet-100 rounded-xl p-3 space-y-3">
              <p className="text-xs font-bold text-violet-700 uppercase tracking-wider flex items-center gap-1.5">
                <Swords className="w-3.5 h-3.5" /> Negotiation Intel
              </p>

              {/* Tactics */}
              {extraction.negotiation_tactics && extraction.negotiation_tactics.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {extraction.negotiation_tactics.map((t, i) => (
                    <span key={i} className="text-[11px] bg-violet-100 text-violet-700 border border-violet-200 px-2 py-0.5 rounded-full font-medium capitalize">
                      {t.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                {/* Power Balance */}
                {extraction.power_balance && (
                  <div className="flex items-center gap-2">
                    <Scale className="w-3.5 h-3.5 text-slate-400" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-[10px] text-slate-500">Power Balance</span>
                        <span className="text-[10px] font-bold text-slate-600">{(extraction.power_balance.score * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-violet-500 rounded-full transition-all"
                          style={{ width: `${extraction.power_balance.score * 100}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5 capitalize">{extraction.power_balance.advantage} advantage</p>
                    </div>
                  </div>
                )}

                {/* BATNA Strength */}
                {extraction.batna_assessment && (
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
                    <div className="flex-1">
                      <p className="text-[10px] text-slate-500 mb-0.5">BATNA Strength</p>
                      <div className="flex items-center gap-2 text-[10px]">
                        <span className="text-blue-600 font-semibold">Buyer {(extraction.batna_assessment.buyer_strength * 100).toFixed(0)}%</span>
                        <span className="text-slate-300">/</span>
                        <span className="text-orange-600 font-semibold">Supplier {(extraction.batna_assessment.supplier_strength * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom row: escalation + bargaining style */}
              <div className="flex items-center gap-3 flex-wrap">
                {extraction.escalation_level && (
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                    extraction.escalation_level === 'high' ? 'bg-red-100 text-red-700' :
                    extraction.escalation_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    <AlertTriangle className="w-3 h-3 inline mr-0.5 -mt-0.5" />
                    {extraction.escalation_level} escalation
                  </span>
                )}
                {extraction.bargaining_style && (
                  <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 capitalize">
                    {extraction.bargaining_style}
                  </span>
                )}
                {extraction.issues_on_table && extraction.issues_on_table.length > 0 && (
                  <span className="text-[10px] text-slate-400">{extraction.issues_on_table.length} issue{extraction.issues_on_table.length > 1 ? 's' : ''} on table</span>
                )}
              </div>
            </div>
          )}

          <div className="flex items-center gap-5 text-xs text-slate-400 pt-2 border-t border-slate-100">
            <span>
              Confidence{' '}
              <span className="font-bold text-slate-600">
                {(extraction.confidence * 100).toFixed(0)}%
              </span>
            </span>
            <span>
              Model{' '}
              <span className="font-bold text-slate-600">{extraction.model_name}</span>
            </span>
            <span>
              Latency{' '}
              <span className="font-bold text-slate-600">{extraction.latency_ms}ms</span>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
