import { useMemo, useRef, useState, useEffect } from 'react'
import { AlertTriangle, Flag, Target, Sparkles } from 'lucide-react'
import type { SegmentPair } from '../api/client'

interface Props {
  segments: SegmentPair[]
  durationMs?: number
  onSeek?: (timestampMs: number) => void
  activeTimestampMs?: number
}

function tsToMs(ts?: string): number {
  if (!ts) return 0
  const parts = ts.split(':').map(p => parseInt(p, 10))
  if (parts.length === 3) return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000
  if (parts.length === 2) return (parts[0] * 60 + parts[1]) * 1000
  return parseInt(ts, 10) || 0
}

function segmentTs(pair: SegmentPair): string {
  const seg = pair.segment as unknown as { timestamp_str?: string; timestamp?: string }
  return seg?.timestamp_str || seg?.timestamp || ''
}

/**
 * Cinematic timeline with colored lanes per extraction type.
 *
 * Lanes (top → bottom):
 *   - risk score (continuous amber → red heat)
 *   - objections (orange markers)
 *   - decision signals (emerald markers)
 *   - topic flags (violet pills, hover = full topic name)
 */
export function DealTimeline({ segments, durationMs, onSeek, activeTimestampMs }: Props) {
  const [hover, setHover] = useState<{ x: number; pair: SegmentPair } | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  const total = useMemo(() => {
    if (durationMs && durationMs > 0) return durationMs
    let max = 0
    for (const p of segments) {
      const ms = tsToMs(segmentTs(p))
      if (ms > max) max = ms
    }
    return Math.max(max, 60_000)
  }, [segments, durationMs])

  const ordered = useMemo(
    () => [...segments].sort((a, b) => tsToMs(segmentTs(a)) - tsToMs(segmentTs(b))),
    [segments],
  )

  const pct = (ms: number) => (ms / total) * 100

  const handleClick = (ms: number) => {
    onSeek?.(ms)
  }

  return (
    <div className="relative rounded-2xl border border-white/5 bg-gradient-to-b from-[#0a0f1e] to-[#060912] p-4 shadow-[0_8px_32px_rgba(2,6,23,0.4)]">
      <div className="flex items-center justify-between mb-3 px-1">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">Deal Timeline</p>
        <div className="flex gap-3 text-[10px] text-slate-400">
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-red-500" />High</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-amber-400" />Medium</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />Low</span>
        </div>
      </div>

      <div
        ref={ref}
        className="relative select-none cursor-pointer"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const x = e.clientX - rect.left
          const frac = Math.max(0, Math.min(1, x / rect.width))
          const ms = frac * total
          let nearest: SegmentPair | null = null
          let bestDelta = Infinity
          for (const p of ordered) {
            const d = Math.abs(tsToMs(segmentTs(p)) - ms)
            if (d < bestDelta) { bestDelta = d; nearest = p }
          }
          if (nearest) setHover({ x, pair: nearest })
        }}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const frac = (e.clientX - rect.left) / rect.width
          handleClick(Math.max(0, frac * total))
        }}
      >
        {/* Risk heat lane */}
        <div className="relative h-10 rounded-xl bg-white/[0.02] overflow-hidden border border-white/5">
          {ordered.map((p, i) => {
            const ms = tsToMs(segmentTs(p))
            const nextMs = i + 1 < ordered.length ? tsToMs(segmentTs(ordered[i + 1])) : total
            const width = Math.max(0.4, ((nextMs - ms) / total) * 100)
            const score = p.extraction.risk_score ?? 0
            const hue = score > 0.6 ? '0' : score > 0.3 ? '38' : '142'
            const alpha = Math.max(0.2, Math.min(0.9, 0.2 + score * 0.7))
            return (
              <div
                key={`r-${i}`}
                className="absolute top-0 bottom-0 transition-opacity"
                style={{
                  left: `${pct(ms)}%`,
                  width: `${width}%`,
                  background: `hsla(${hue}, 85%, 55%, ${alpha})`,
                }}
                title={`${segmentTs(p)} — risk ${Math.round(score * 100)}%`}
              />
            )
          })}
        </div>

        {/* Objections lane */}
        <div className="relative h-6 mt-1.5 rounded-lg bg-white/[0.02] overflow-hidden border border-white/5">
          {ordered.map((p, i) => {
            const objs = p.extraction.objections || []
            if (!objs.length) return null
            const ms = tsToMs(segmentTs(p))
            return (
              <div
                key={`o-${i}`}
                className="absolute top-0 bottom-0 w-1.5 bg-orange-400 shadow-[0_0_10px_rgba(251,146,60,0.6)]"
                style={{ left: `${pct(ms)}%` }}
                title={`${segmentTs(p)} — ${objs.length} objection${objs.length === 1 ? '' : 's'}`}
              />
            )
          })}
          <span className="absolute left-1.5 top-0.5 text-[9px] font-bold uppercase tracking-wider text-orange-300/70 pointer-events-none">Objections</span>
        </div>

        {/* Decision signals lane */}
        <div className="relative h-6 mt-1.5 rounded-lg bg-white/[0.02] overflow-hidden border border-white/5">
          {ordered.map((p, i) => {
            const sigs = p.extraction.decision_signals || []
            if (!sigs.length) return null
            const ms = tsToMs(segmentTs(p))
            return (
              <div
                key={`s-${i}`}
                className="absolute top-0 bottom-0 w-1.5 bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.6)]"
                style={{ left: `${pct(ms)}%` }}
                title={`${segmentTs(p)} — decision signal`}
              />
            )
          })}
          <span className="absolute left-1.5 top-0.5 text-[9px] font-bold uppercase tracking-wider text-emerald-300/70 pointer-events-none">Signals</span>
        </div>

        {/* Playhead */}
        {activeTimestampMs != null && activeTimestampMs > 0 && (
          <div
            className="absolute top-0 bottom-0 w-[2px] bg-white/90 shadow-[0_0_12px_rgba(255,255,255,0.9)] pointer-events-none"
            style={{ left: `${pct(activeTimestampMs)}%` }}
          />
        )}

        {/* Hover tooltip */}
        {hover && (
          <div
            className="pointer-events-none absolute -top-2 -translate-y-full -translate-x-1/2 whitespace-nowrap rounded-lg bg-[#111827] px-3 py-2 text-[11px] text-slate-200 border border-white/10 shadow-xl"
            style={{ left: Math.max(60, Math.min((ref.current?.clientWidth ?? 600) - 60, hover.x)) }}
          >
            <div className="flex items-center gap-2 font-mono text-amber-300">
              <Flag className="w-3 h-3" />{segmentTs(hover.pair)}
            </div>
            <div className="mt-0.5 capitalize text-slate-200 font-semibold">{hover.pair.extraction.topic}</div>
            <div className="text-slate-400 text-[10px]">Risk {Math.round((hover.pair.extraction.risk_score ?? 0) * 100)}%</div>
            {(hover.pair.extraction.objections?.length ?? 0) > 0 && (
              <div className="mt-1 flex items-center gap-1 text-orange-300 text-[10px]">
                <AlertTriangle className="w-3 h-3" />
                {hover.pair.extraction.objections!.length} objection{hover.pair.extraction.objections!.length === 1 ? '' : 's'}
              </div>
            )}
            {(hover.pair.extraction.decision_signals?.length ?? 0) > 0 && (
              <div className="flex items-center gap-1 text-emerald-300 text-[10px]">
                <Target className="w-3 h-3" />
                signal
              </div>
            )}
          </div>
        )}
      </div>

      {/* Axis ticks */}
      <div className="mt-2 flex justify-between text-[9px] font-mono text-slate-500 px-1">
        <span>00:00</span>
        <span className="flex items-center gap-1 text-slate-400"><Sparkles className="w-3 h-3 text-indigo-400" />Click to seek</span>
        <span>{fmtMs(total)}</span>
      </div>
    </div>
  )
}

function fmtMs(ms: number): string {
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}
