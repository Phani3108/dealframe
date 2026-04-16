import { useState } from 'react'
import { X, Save, Loader2 } from 'lucide-react'
import { submitCorrection, type SegmentPair } from '../api/client'

interface Props {
  jobId: string
  pair: SegmentPair
  segmentIndex: number
  onClose: () => void
}

/** Minimal correction modal. Edit the LLM's extraction, save, flywheel picks it up. */
export function CorrectionDialog({ jobId, pair, segmentIndex, onClose }: Props) {
  const e = pair.extraction
  const seg = pair.segment as unknown as { timestamp_str?: string; transcript?: string }
  const ts = seg?.timestamp_str
    || (pair as unknown as { timestamp?: string }).timestamp
    || ''
  const [topic, setTopic] = useState(e.topic ?? '')
  const [sentiment, setSentiment] = useState(e.sentiment ?? 'neutral')
  const [risk, setRisk] = useState<'low' | 'medium' | 'high'>((e.risk as 'low' | 'medium' | 'high') ?? 'low')
  const [riskScore, setRiskScore] = useState(Math.round((e.risk_score ?? 0) * 100))
  const [objections, setObjections] = useState((e.objections ?? []).join('\n'))
  const [signals, setSignals] = useState((e.decision_signals ?? []).join('\n'))
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await submitCorrection({
        job_id: jobId,
        segment_index: segmentIndex,
        timestamp_str: ts,
        transcript: seg?.transcript ?? '',
        original: e as unknown as Record<string, unknown>,
        corrected: {
          topic,
          sentiment,
          risk,
          risk_score: riskScore / 100,
          objections: objections.split('\n').map(s => s.trim()).filter(Boolean),
          decision_signals: signals.split('\n').map(s => s.trim()).filter(Boolean),
        },
        notes,
      })
      setSaved(true)
      setTimeout(onClose, 900)
    } catch (err) {
      alert(`Failed: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[70] flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-xl rounded-2xl shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-indigo-600">Correct extraction</p>
            <p className="font-mono text-xs text-slate-500">{ts} · segment #{segmentIndex}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {seg?.transcript && (
            <div className="text-xs bg-slate-50 border border-slate-100 rounded-lg px-3 py-2 text-slate-600">
              {seg.transcript}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Topic</label>
              <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" value={topic} onChange={ev => setTopic(ev.target.value)} />
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Sentiment</label>
              <select className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white" value={sentiment} onChange={ev => setSentiment(ev.target.value)}>
                <option value="positive">positive</option>
                <option value="neutral">neutral</option>
                <option value="hesitant">hesitant</option>
                <option value="negative">negative</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Risk</label>
              <select className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white" value={risk} onChange={ev => setRisk(ev.target.value as 'low' | 'medium' | 'high')}>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Risk score ({riskScore}%)</label>
              <input type="range" min={0} max={100} value={riskScore} onChange={ev => setRiskScore(parseInt(ev.target.value, 10))} className="w-full" />
            </div>
          </div>

          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Objections (one per line)</label>
            <textarea rows={3} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono" value={objections} onChange={ev => setObjections(ev.target.value)} />
          </div>
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Decision signals (one per line)</label>
            <textarea rows={3} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono" value={signals} onChange={ev => setSignals(ev.target.value)} />
          </div>
          <div>
            <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1 block">Notes (optional)</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" value={notes} onChange={ev => setNotes(ev.target.value)} placeholder="Why is this correction needed?" />
          </div>
        </div>

        <div className="px-5 py-4 border-t border-slate-100 flex items-center justify-between sticky bottom-0 bg-white">
          <p className="text-[11px] text-slate-500">
            Corrections feed the <span className="font-semibold text-indigo-600">Flywheel</span> trainer.
          </p>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-2 rounded-lg text-slate-600 text-sm hover:bg-slate-50">Cancel</button>
            <button
              onClick={save}
              disabled={saving || saved}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white ${
                saved ? 'bg-emerald-500' : 'bg-indigo-600 hover:bg-indigo-700'
              } disabled:opacity-60`}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saved ? 'Saved!' : 'Save correction'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
