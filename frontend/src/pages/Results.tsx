import { useState, useEffect, useMemo, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Clock, FileVideo, AlertTriangle, TrendingUp, Loader2, Swords, Scale, Target, ArrowRightLeft, Share2, FileDown, MessageSquare, Film } from 'lucide-react'
import { SegmentCard } from '../components/SegmentCard'
import { DealTimeline } from '../components/DealTimeline'
import { DealChat } from '../components/DealChat'
import { CorrectionDialog } from '../components/CorrectionDialog'
import {
  getJob, getSpeakers, createSummary, listClips, extractSignificantClips,
  createShareLink, downloadDealBrief,
  type Job, type SegmentPair,
} from '../api/client'

type Tab = 'segments' | 'summary' | 'clips' | 'speakers' | 'negotiation'
const SUMMARY_TYPES = ['executive', 'action_items', 'meeting_notes', 'deal_brief']

function RiskMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score > 0.6 ? 'bg-red-500' : score > 0.3 ? 'bg-amber-400' : 'bg-emerald-500'
  const textColor = score > 0.6 ? 'text-red-600' : score > 0.3 ? 'text-amber-600' : 'text-emerald-600'
  return (
    <div className="text-right">
      <p className="text-xs text-slate-500 mb-1">Overall risk</p>
      <p className={`text-3xl font-bold tabular-nums ${textColor}`}>{pct}%</p>
      <div className="w-24 h-1.5 bg-slate-100 rounded-full mt-1.5 ml-auto overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Results() {
  const { jobId } = useParams<{ jobId: string }>()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('segments')
  const [currentMs, setCurrentMs] = useState(0)
  const [showChat, setShowChat] = useState(true)
  const [correctTarget, setCorrectTarget] = useState<SegmentPair | null>(null)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  // Summary
  const [summaryType, setSummaryType] = useState('executive')
  const [summaryContent, setSummaryContent] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)

  // Clips
  const [clips, setClips] = useState<Array<{ filename: string; segment_index: number; url: string }>>([])
  const [clipsLoading, setClipsLoading] = useState(false)
  const [sigLoading, setSigLoading] = useState(false)

  // Speakers
  const [speakers, setSpeakers] = useState<Array<{ speaker: string; turns: number; words: number; percentage: number }>>([])
  const [speakersLoading, setSpeakersLoading] = useState(false)

  useEffect(() => {
    if (!jobId) return
    getJob(jobId)
      .then(setJob)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [jobId])

  const loadSummary = async () => {
    if (!jobId) return
    setSummaryLoading(true)
    try {
      const d = await createSummary(jobId, summaryType)
      setSummaryContent(d.content)
    } catch { /* ignore */ }
    finally { setSummaryLoading(false) }
  }

  const loadClips = async () => {
    if (!jobId) return
    setClipsLoading(true)
    try {
      const d = await listClips(jobId)
      setClips(d.clips ?? [])
    } catch { /* ignore */ }
    finally { setClipsLoading(false) }
  }

  const loadSpeakers = async () => {
    if (!jobId) return
    setSpeakersLoading(true)
    try {
      const d = await getSpeakers(jobId)
      setSpeakers(d.speakers ?? [])
    } catch { /* ignore */ }
    finally { setSpeakersLoading(false) }
  }

  const extractSig = async () => {
    if (!jobId) return
    setSigLoading(true)
    try {
      const d = await extractSignificantClips(jobId, 3)
      // reload clips after extraction
      const d2 = await listClips(jobId)
      setClips(d2.clips ?? [])
    } catch { /* ignore */ }
    finally { setSigLoading(false) }
  }

  const onTabChange = (t: Tab) => {
    setTab(t)
    if (t === 'summary' && !summaryContent) loadSummary()
    if (t === 'clips' && clips.length === 0) loadClips()
    if (t === 'speakers' && speakers.length === 0) loadSpeakers()
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-6 lg:p-8 flex items-center gap-3 text-slate-400">
        <div className="w-4 h-4 border-2 border-slate-300 border-t-indigo-500 rounded-full animate-spin" />
        Loading results…
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="p-4 sm:p-6 lg:p-8">
        <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <div className="card p-8 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-slate-600">{error || 'Job not found'}</p>
        </div>
      </div>
    )
  }

  const intel = job.result
  const segments = intel?.segments ?? []
  const highRiskCount = segments.filter(p => p.extraction.risk === 'high').length

  const seek = (ts: string | number) => {
    const ms = typeof ts === 'number'
      ? ts
      : (() => {
          const parts = ts.split(':').map(n => parseInt(n, 10))
          if (parts.length === 3) return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000
          if (parts.length === 2) return (parts[0] * 60 + parts[1]) * 1000
          return 0
        })()
    setCurrentMs(ms)
    const v = videoRef.current
    if (v) {
      try { v.currentTime = Math.max(0, ms / 1000); v.play().catch(() => {}) } catch { /* ignore */ }
    }
  }

  const handleShare = async () => {
    if (!jobId) return
    try {
      const r = await createShareLink(jobId, 168)
      setShareUrl(r.link.url)
      try { await navigator.clipboard.writeText(r.link.url) } catch { /* ignore */ }
    } catch { /* ignore */ }
  }

  const videoSrc = (job as Job & { video_path?: string; source_url?: string }).source_url
    || (jobId ? `/api/v1/stream/video/${jobId}` : undefined)

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in">
      {/* Back */}
      <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6 group">
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Dashboard
      </Link>

      {/* Header card */}
      <div className="card p-6 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <FileVideo className="w-5 h-5 text-indigo-500" />
              <h1 className="text-lg font-bold text-slate-900">Analysis Results</h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-500 font-mono">
              <span>{jobId}</span>
              {intel && (
                <span className="flex items-center gap-1 font-sans">
                  <Clock className="w-3.5 h-3.5" />
                  {Math.round((intel.duration_ms ?? 0) / 1000)}s
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={handleShare}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200"
              title="Create a shareable read-only link"
            >
              <Share2 className="w-3.5 h-3.5" /> Share
            </button>
            <a
              href={jobId ? downloadDealBrief(jobId) : '#'}
              target="_blank" rel="noreferrer"
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200"
              title="Download a printable deal brief"
            >
              <FileDown className="w-3.5 h-3.5" /> Brief
            </a>
            <button
              onClick={() => setShowChat(v => !v)}
              className={`flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl ${
                showChat ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
              title="Toggle chat panel"
            >
              <MessageSquare className="w-3.5 h-3.5" /> Chat
            </button>
            {highRiskCount > 0 && (
              <div className="text-right">
                <p className="text-xs text-slate-500">High risk</p>
                <p className="text-2xl font-bold text-red-600 tabular-nums">{highRiskCount}</p>
              </div>
            )}
            {intel?.overall_risk_score != null && (
              <RiskMeter score={intel.overall_risk_score} />
            )}
          </div>
        </div>
        {shareUrl && (
          <p className="mt-3 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 font-mono break-all">
            Share link copied: {shareUrl}
          </p>
        )}
      </div>

      {/* Cinematic timeline + video player row */}
      {job.status === 'completed' && segments.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2 space-y-3">
            <div className="relative rounded-2xl overflow-hidden bg-black border border-white/5">
              {videoSrc ? (
                <video
                  ref={videoRef}
                  src={videoSrc}
                  controls
                  className="w-full aspect-video"
                  onTimeUpdate={(e) => setCurrentMs(Math.round(e.currentTarget.currentTime * 1000))}
                />
              ) : (
                <div className="w-full aspect-video flex items-center justify-center text-slate-500 text-sm">
                  <Film className="w-8 h-8 mr-2" />
                  Video preview unavailable
                </div>
              )}
            </div>
            <DealTimeline
              segments={segments}
              durationMs={(intel?.duration_ms as number | undefined) ?? undefined}
              onSeek={(ms) => seek(ms)}
              activeTimestampMs={currentMs}
            />
          </div>
          {showChat && jobId && (
            <div className="lg:col-span-1 h-[520px]">
              <DealChat
                jobId={jobId}
                onCitationClick={(ts) => seek(ts)}
              />
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 mb-6">
        {(['segments', 'summary', 'clips', 'speakers', 'negotiation'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => onTabChange(t)}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              tab === t ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t === 'negotiation' ? 'Negotiation' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Status */}
      {job.status !== 'completed' ? (
        <div className="card p-10 text-center">
          <p className="text-slate-500">
            Status: <span className="font-semibold text-slate-800 capitalize">{job.status}</span>
          </p>
          {job.status === 'failed' && job.error && (
            <p className="text-sm text-red-600 mt-2">{job.error}</p>
          )}
        </div>
      ) : tab === 'segments' ? (
        segments.length === 0 ? (
          <div className="card p-10 text-center">
            <TrendingUp className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-slate-400 text-sm">No segments found in this video.</p>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-6 mb-4 text-sm text-slate-500">
              <span>{segments.length} segment{segments.length !== 1 ? 's' : ''} analyzed</span>
              {highRiskCount > 0 && (
                <span className="flex items-center gap-1 text-red-600 font-medium">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {highRiskCount} high risk
                </span>
              )}
              <span className="ml-auto">Scroll to explore</span>
            </div>
            <div className="space-y-3">
              {segments.map((pair, i) => (
                <div key={i} className="group relative">
                  <SegmentCard pair={pair} />
                  <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                    <button
                      onClick={() => {
                        const ts = (pair.segment as unknown as { timestamp_str?: string }).timestamp_str
                          || (pair as unknown as { timestamp?: string }).timestamp
                        if (ts) seek(ts)
                      }}
                      className="text-[10px] font-medium px-2 py-1 rounded-md bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200"
                    >
                      Seek
                    </button>
                    <button
                      onClick={() => setCorrectTarget(pair)}
                      className="text-[10px] font-medium px-2 py-1 rounded-md bg-slate-50 text-slate-700 hover:bg-slate-100 border border-slate-200"
                      title="Correct this extraction (feeds the training flywheel)"
                    >
                      Correct
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )
      ) : tab === 'summary' ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <select
              className="border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white"
              value={summaryType}
              onChange={e => { setSummaryType(e.target.value); setSummaryContent('') }}
            >
              {SUMMARY_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
            <button
              onClick={loadSummary}
              disabled={summaryLoading}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
            >
              {summaryLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Generate'}
            </button>
          </div>
          {summaryContent && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed">{summaryContent}</pre>
            </div>
          )}
        </div>
      ) : tab === 'clips' ? (
        <div className="space-y-4">
          <div className="flex gap-3">
            <button
              onClick={loadClips}
              disabled={clipsLoading}
              className="px-4 py-2 bg-slate-100 text-slate-700 text-sm rounded-xl hover:bg-slate-200 flex items-center gap-2"
            >
              {clipsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Refresh'}
            </button>
            <button
              onClick={extractSig}
              disabled={sigLoading}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
            >
              {sigLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Extract Top 3 Clips'}
            </button>
          </div>
          {clips.length === 0
            ? <p className="text-sm text-slate-400 card p-6 text-center">No clips extracted yet.</p>
            : (
              <div className="space-y-2">
                {clips.map((c, i) => (
                  <div key={i} className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center gap-3 text-sm">
                    <span className="text-slate-400 font-mono">#{c.segment_index}</span>
                    <span className="flex-1 text-slate-700 font-medium">{c.filename}</span>
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-600 hover:underline text-xs"
                    >
                      Download
                    </a>
                  </div>
                ))}
              </div>
            )}
        </div>
      ) : tab === 'speakers' ? (
        /* Speakers tab */
        <div className="space-y-4">
          {speakersLoading
            ? <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
            : speakers.length === 0
            ? <p className="text-sm text-slate-400 card p-6 text-center">No speaker data available.</p>
            : (
              <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Speaker</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500">Talk %</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500">Turns</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500">Words</th>
                    </tr>
                  </thead>
                  <tbody>
                    {speakers.map(s => (
                      <tr key={s.speaker} className="border-b border-slate-100 last:border-0">
                        <td className="px-4 py-3 font-medium text-slate-800">{s.speaker}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-20 bg-slate-100 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-indigo-400" style={{ width: `${s.percentage}%` }} />
                            </div>
                            <span className="text-slate-600">{s.percentage.toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-slate-600">{s.turns}</td>
                        <td className="px-4 py-3 text-right text-slate-600">{s.words.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>
      ) : (
        /* Negotiation Report tab */
        <NegotiationReport segments={segments} />
      )}

      {correctTarget && jobId && (
        <CorrectionDialog
          jobId={jobId}
          pair={correctTarget}
          segmentIndex={segments.indexOf(correctTarget)}
          onClose={() => setCorrectTarget(null)}
        />
      )}
    </div>
  )
}

/* ─── Negotiation Report Component ─────────────────────────────────────────── */

function NegotiationReport({ segments }: { segments: SegmentPair[] }) {
  // Aggregate negotiation intel across all segments
  const report = useMemo(() => {
    const allTactics: Record<string, number> = {}
    let powerSum = 0, powerCount = 0
    let buyerBatnaSum = 0, supplierBatnaSum = 0, batnaCount = 0
    const escalationLevels: string[] = []
    const styles: Record<string, number> = {}
    const allIssues = new Set<string>()
    let integrativeCount = 0

    for (const { extraction } of segments) {
      if (extraction.negotiation_tactics) {
        for (const t of extraction.negotiation_tactics) {
          allTactics[t] = (allTactics[t] || 0) + 1
        }
      }
      if (extraction.power_balance) {
        powerSum += extraction.power_balance.score
        powerCount++
      }
      if (extraction.batna_assessment) {
        buyerBatnaSum += extraction.batna_assessment.buyer_strength
        supplierBatnaSum += extraction.batna_assessment.supplier_strength
        batnaCount++
      }
      if (extraction.escalation_level) {
        escalationLevels.push(extraction.escalation_level)
      }
      if (extraction.bargaining_style) {
        styles[extraction.bargaining_style] = (styles[extraction.bargaining_style] || 0) + 1
      }
      if (extraction.issues_on_table) {
        extraction.issues_on_table.forEach(i => allIssues.add(i))
      }
      if (extraction.integrative_signals?.length) {
        integrativeCount += extraction.integrative_signals.length
      }
    }

    const topTactics = Object.entries(allTactics)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)

    const avgPower = powerCount > 0 ? powerSum / powerCount : null
    const avgBuyerBatna = batnaCount > 0 ? buyerBatnaSum / batnaCount : null
    const avgSupplierBatna = batnaCount > 0 ? supplierBatnaSum / batnaCount : null

    const peakEscalation = escalationLevels.includes('high')
      ? 'high' : escalationLevels.includes('medium')
      ? 'medium' : escalationLevels.length > 0
      ? 'low' : null

    const dominantStyle = Object.entries(styles).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null

    return { topTactics, avgPower, avgBuyerBatna, avgSupplierBatna, peakEscalation, dominantStyle, allIssues: [...allIssues], integrativeCount, hasData: Object.keys(allTactics).length > 0 || powerCount > 0 }
  }, [segments])

  if (!report.hasData) {
    return (
      <div className="card p-10 text-center">
        <Swords className="w-8 h-8 text-slate-300 mx-auto mb-2" />
        <p className="text-slate-400 text-sm">No negotiation intelligence available for this session.</p>
        <p className="text-xs text-slate-300 mt-1">Process a video with the Procurement vertical enabled to see intelligence here.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Top row: Power + BATNA + Escalation */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Power Balance */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Scale className="w-4 h-4 text-violet-500" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Avg Power Balance</h3>
          </div>
          {report.avgPower !== null ? (
            <>
              <p className="text-3xl font-bold text-violet-600 tabular-nums">{(report.avgPower * 100).toFixed(0)}%</p>
              <div className="h-2 bg-slate-100 rounded-full mt-2 overflow-hidden">
                <div className="h-full bg-gradient-to-r from-violet-400 to-violet-600 rounded-full" style={{ width: `${report.avgPower * 100}%` }} />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">{report.avgPower > 0.55 ? 'Buyer advantage' : report.avgPower < 0.45 ? 'Supplier advantage' : 'Balanced'}</p>
            </>
          ) : <p className="text-sm text-slate-400">N/A</p>}
        </div>

        {/* BATNA */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-indigo-500" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">BATNA Strength</h3>
          </div>
          {report.avgBuyerBatna !== null && report.avgSupplierBatna !== null ? (
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-blue-600 font-semibold">Buyer</span>
                  <span className="text-slate-500">{(report.avgBuyerBatna * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-400 rounded-full" style={{ width: `${report.avgBuyerBatna * 100}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-orange-600 font-semibold">Supplier</span>
                  <span className="text-slate-500">{(report.avgSupplierBatna * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-orange-400 rounded-full" style={{ width: `${report.avgSupplierBatna * 100}%` }} />
                </div>
              </div>
            </div>
          ) : <p className="text-sm text-slate-400">N/A</p>}
        </div>

        {/* Escalation + Style */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <ArrowRightLeft className="w-4 h-4 text-amber-500" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Dynamics</h3>
          </div>
          <div className="space-y-2.5">
            {report.peakEscalation && (
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500">Peak Escalation</span>
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                  report.peakEscalation === 'high' ? 'bg-red-100 text-red-700' :
                  report.peakEscalation === 'medium' ? 'bg-amber-100 text-amber-700' :
                  'bg-slate-100 text-slate-600'
                }`}>{report.peakEscalation}</span>
              </div>
            )}
            {report.dominantStyle && (
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500">Dominant Style</span>
                <span className="text-[11px] font-bold text-indigo-600 capitalize">{report.dominantStyle}</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-500">Integrative Signals</span>
              <span className="text-[11px] font-bold text-emerald-600">{report.integrativeCount}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tactics frequency */}
      {report.topTactics.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Swords className="w-4 h-4 text-violet-500" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Tactics Detected</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {report.topTactics.map(([tactic, count]) => (
              <div key={tactic} className="bg-violet-50 border border-violet-100 rounded-xl px-3 py-2.5">
                <p className="text-sm font-semibold text-violet-700 capitalize">{tactic.replace(/_/g, ' ')}</p>
                <p className="text-xs text-violet-400 mt-0.5">{count} occurrence{count > 1 ? 's' : ''}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Issues on the table */}
      {report.allIssues.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">Issues on the Table</h3>
          <div className="flex flex-wrap gap-2">
            {report.allIssues.map(issue => (
              <span key={issue} className="text-xs bg-slate-100 text-slate-600 border border-slate-200 px-2.5 py-1 rounded-full capitalize">
                {issue.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
