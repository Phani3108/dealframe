import { useState, useEffect } from 'react'
import { Zap, RefreshCw, Plus, CheckCircle2 } from 'lucide-react'
import { Badge } from '../components/Badge'
import {
  listFinetuningRuns,
  getBestModel,
  activateModel,
  getDatasetStats,
  type FinetuningRun,
} from '../api/client'

interface DatasetStats {
  total_examples: number
  class_distribution: Record<string, Record<string, number>>
}

function LossBar({ value, max = 2 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-indigo-400 rounded-full" style={{ width: `${100 - pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-600 w-12 text-right">{value.toFixed(4)}</span>
    </div>
  )
}

export function Finetuning() {
  const [runs, setRuns] = useState<FinetuningRun[]>([])
  const [best, setBest] = useState<FinetuningRun | null>(null)
  const [stats, setStats] = useState<DatasetStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activating, setActivating] = useState<string | null>(null)
  const [activated, setActivated] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.allSettled([
      listFinetuningRuns().then(r => setRuns(r.experiments ?? [])).catch(() => {}),
      getBestModel().then(setBest).catch(() => {}),
      getDatasetStats().then(setStats).catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleActivate = async (id: string) => {
    setActivating(id)
    try {
      await activateModel(id)
      setActivated(id)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Activation failed')
    } finally {
      setActivating(null)
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">Fine-tuning</h1>
          <p className="page-subtitle">LoRA training arc — dataset → train → evaluate → deploy</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-1.5">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Dataset stats */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-indigo-500" />
              Dataset
            </h2>
            {stats ? (
              <>
                <div className="text-3xl font-bold text-slate-900 tabular-nums mb-0.5">
                  {stats.total_examples}
                </div>
                <p className="text-xs text-slate-500 mb-4">training examples</p>
                {Object.entries(stats.class_distribution ?? {}).map(([field, dist]) => (
                  <div key={field} className="mb-3">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                      {field}
                    </p>
                    <div className="space-y-1">
                      {Object.entries(dist).slice(0, 5).map(([label, count]) => (
                        <div key={label} className="flex items-center gap-2 text-xs">
                          <span className="text-slate-600 w-20 truncate capitalize">{label}</span>
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-300 rounded-full"
                              style={{ width: `${Math.min(100, (Number(count) / stats.total_examples) * 100)}%` }}
                            />
                          </div>
                          <span className="text-slate-400 tabular-nums w-6 text-right">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <div className="text-center py-6">
                <p className="text-sm text-slate-400">No dataset yet</p>
                <p className="text-xs text-slate-300 mt-1">Export from DB extractions via API</p>
              </div>
            )}
          </div>

          {/* Best model */}
          {best && (
            <div className="card p-5 border-emerald-200 bg-emerald-50">
              <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mb-2">
                Best Model
              </p>
              <p className="font-semibold text-slate-900">{best.name}</p>
              <div className="mt-2 space-y-1">
                {best.training_metrics && (
                  <>
                    <p className="text-xs text-slate-600">
                      Train loss: <span className="font-semibold">{best.training_metrics.train_loss.toFixed(4)}</span>
                    </p>
                    <p className="text-xs text-slate-600">
                      Val loss: <span className="font-semibold">{best.training_metrics.val_loss.toFixed(4)}</span>
                    </p>
                    <p className="text-xs text-slate-600">
                      Epochs: <span className="font-semibold">{best.training_metrics.epochs_completed}</span>
                    </p>
                  </>
                )}
              </div>
              <button
                onClick={() => handleActivate(best.id)}
                disabled={activating === best.id || activated === best.id}
                className="mt-3 w-full text-xs py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {activated === best.id ? (
                  <><CheckCircle2 className="w-3.5 h-3.5" /> Activated</>
                ) : activating === best.id ? (
                  'Activating…'
                ) : (
                  'Activate Model'
                )}
              </button>
            </div>
          )}
        </div>

        {/* Training runs */}
        <div className="col-span-2">
          <div className="card">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h2 className="text-sm font-semibold text-slate-900">Training Runs</h2>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Plus className="w-3.5 h-3.5" />
                <span>Start via API: POST /api/v1/finetuning/train</span>
              </div>
            </div>

            {runs.length === 0 ? (
              <div className="p-12 text-center">
                <Zap className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                <p className="text-sm text-slate-400">No training runs yet</p>
                <p className="text-xs text-slate-300 mt-1">
                  Export a dataset first, then kick off training via the API
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {runs.map(run => (
                  <div key={run.id} className="px-5 py-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-semibold text-slate-900">{run.name}</p>
                          <Badge label={run.status} />
                          {activated === run.id && (
                            <Badge label="activated" className="bg-emerald-50 text-emerald-700 border-emerald-200" />
                          )}
                        </div>
                        <p className="text-xs font-mono text-slate-400">{run.id}</p>
                      </div>
                      {(run.status === 'completed' && activated !== run.id) && (
                        <button
                          onClick={() => handleActivate(run.id)}
                          disabled={activating === run.id}
                          className="text-xs btn-secondary"
                        >
                          {activating === run.id ? 'Activating…' : 'Activate'}
                        </button>
                      )}
                    </div>

                    {run.training_metrics && (
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <p className="text-xs text-slate-400 mb-1">Train loss</p>
                          <LossBar value={run.training_metrics.train_loss} />
                        </div>
                        <div>
                          <p className="text-xs text-slate-400 mb-1">Val loss</p>
                          <LossBar value={run.training_metrics.val_loss} />
                        </div>
                        <div>
                          <p className="text-xs text-slate-400 mb-1">Epochs</p>
                          <p className="text-sm font-semibold text-slate-700 tabular-nums">
                            {run.training_metrics.epochs_completed}
                          </p>
                        </div>
                      </div>
                    )}

                    {run.error && (
                      <p className="text-xs text-red-600 mt-2">{run.error}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
