import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { RiskBadge, Badge } from './Badge'
import type { SegmentPair } from '../api/client'

export function msToTimestamp(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

const riskBorder: Record<string, string> = {
  high: 'border-l-red-500',
  medium: 'border-l-amber-400',
  low: 'border-l-emerald-500',
}

export function SegmentCard({ pair }: { pair: SegmentPair }) {
  const [expanded, setExpanded] = useState(false)
  const { segment, extraction } = pair

  return (
    <div
      className={`bg-white border border-slate-200 border-l-4 ${riskBorder[extraction.risk] ?? 'border-l-slate-300'} rounded-xl p-4 hover:shadow-sm transition-shadow`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span className="text-xs font-mono text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
              {msToTimestamp(segment.timestamp_ms)}
            </span>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-100 text-xs px-2 py-0.5 rounded-full font-medium capitalize">
              {extraction.topic}
            </span>
            <span className="bg-slate-50 text-slate-600 border border-slate-200 text-xs px-2 py-0.5 rounded-full capitalize">
              {extraction.sentiment}
            </span>
            <RiskBadge risk={extraction.risk} />
            <span className="text-xs text-slate-400 ml-auto tabular-nums">
              {(extraction.risk_score * 100).toFixed(0)}% risk
            </span>
          </div>
          <p className="text-sm text-slate-700 leading-relaxed line-clamp-2">
            {segment.transcript || <em className="text-slate-400">No transcript</em>}
          </p>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-slate-300 hover:text-slate-500 flex-shrink-0 p-1 rounded transition-colors"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
          {extraction.objections.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-600 mb-1.5 uppercase tracking-wide">
                Objections
              </p>
              <ul className="space-y-1">
                {extraction.objections.map((o, i) => (
                  <li key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                    <span className="text-red-400 mt-0.5 flex-shrink-0">•</span>
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {extraction.decision_signals.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-emerald-600 mb-1.5 uppercase tracking-wide">
                Decision Signals
              </p>
              <ul className="space-y-1">
                {extraction.decision_signals.map((s, i) => (
                  <li key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                    <span className="text-emerald-400 mt-0.5 flex-shrink-0">•</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-slate-400 pt-1">
            <span>
              Confidence{' '}
              <span className="font-semibold text-slate-600">
                {(extraction.confidence * 100).toFixed(0)}%
              </span>
            </span>
            <span>
              Model{' '}
              <span className="font-semibold text-slate-600">{extraction.model_name}</span>
            </span>
            <span>
              Latency{' '}
              <span className="font-semibold text-slate-600">{extraction.latency_ms}ms</span>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
