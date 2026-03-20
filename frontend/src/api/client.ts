// ─── Types ────────────────────────────────────────────────────────────────────

export interface ExtractionResult {
  topic: string
  sentiment: string
  risk: 'low' | 'medium' | 'high'
  risk_score: number
  objections: string[]
  decision_signals: string[]
  confidence: number
  model_name: string
  latency_ms: number
}

export interface AlignedSegment {
  timestamp_ms: number
  transcript: string
}

export interface SegmentPair {
  segment: AlignedSegment
  extraction: ExtractionResult
}

export interface VideoIntelligence {
  video_path: string
  duration_ms: number
  overall_risk_score: number
  segments: SegmentPair[]
}

export interface Job {
  job_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at?: string
  result?: VideoIntelligence
  error?: string
}

export interface Objection {
  text: string
  count: number
  risk_avg: number
}

export interface TopicTrend {
  topic: string
  daily_counts: Record<string, number>
}

export interface RiskSummary {
  high: number
  medium: number
  low: number
  average_score: number
}

export interface LocalStatus {
  whisper_available: boolean
  whisper_model: string
  qwen_vl_available: boolean
  finetuned_adapter_available: boolean
  adapter_path: string | null
  active_extractor: string
  cost_per_video_usd: number
}

export interface ObservatorySession {
  session_id: string
  status: string
  models?: string[]
  agreement_score?: number
  report?: {
    overall_agreement: number
    pairwise_topic_agreement: Record<string, number>
    model_stats: Record<string, { avg_confidence: number; avg_latency_ms: number }>
  }
  created_at?: string
}

export interface FinetuningRun {
  id: string
  name: string
  status: string
  created_at: string
  adapter_path?: string
  dataset_path?: string
  training_metrics?: {
    train_loss: number
    val_loss: number
    epochs_completed: number
    total_steps: number
  }
  error?: string
}

export interface BenchmarkComparison {
  local: { total_latency_ms: number; model_name: string }
  api: { total_latency_ms: number; model_name: string }
  latency_ratio: number
  local_is_faster: boolean
  cost_savings_usd: number
  verdict: string
}

// ─── HTTP helper ─────────────────────────────────────────────────────────────

const BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ─── Process ──────────────────────────────────────────────────────────────────

export const processVideo = (file: File, useVision = false) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ job_id: string; status: string }>(
    `/process?use_vision=${useVision}`,
    { method: 'POST', body: form },
  )
}

export const getJob = (jobId: string) => request<Job>(`/jobs/${jobId}`)

export const listJobs = () =>
  request<{ jobs: Job[]; total: number }>('/jobs')

// ─── Observatory ─────────────────────────────────────────────────────────────

export const startObservatory = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ session_id: string; status: string }>(
    '/observatory/compare',
    { method: 'POST', body: form },
  )
}

export const getObservatorySession = (id: string) =>
  request<ObservatorySession>(`/observatory/sessions/${id}`)

export const listObservatorySessions = () =>
  request<{ sessions: ObservatorySession[]; total: number }>('/observatory/sessions')

// ─── Intelligence ─────────────────────────────────────────────────────────────

export const getObjections = (limit = 10) =>
  request<{ objections: Objection[] }>(`/intelligence/objections?limit=${limit}`)

export const getTopicTrends = () =>
  request<{ topics: TopicTrend[] }>('/intelligence/topics/trend')

export const getRiskSummary = () =>
  request<RiskSummary>('/intelligence/risk/summary')

// ─── Fine-tuning ─────────────────────────────────────────────────────────────

export const getDatasetStats = () =>
  request<{
    total_examples: number
    class_distribution: Record<string, Record<string, number>>
  }>('/finetuning/dataset/stats')

export const startTraining = (
  name: string,
  trainPath: string,
  valPath: string,
  dryRun = false,
) => request<{ experiment_id: string; status: string }>(
  `/finetuning/train?name=${encodeURIComponent(name)}&train_path=${encodeURIComponent(trainPath)}&val_path=${encodeURIComponent(valPath)}&dry_run=${dryRun}`,
  { method: 'POST' },
)

export const listFinetuningRuns = () =>
  request<{ experiments: FinetuningRun[]; total: number }>('/finetuning/runs')

export const getFinetuningRun = (id: string) =>
  request<FinetuningRun>(`/finetuning/runs/${id}`)

export const getBestModel = () =>
  request<FinetuningRun>('/finetuning/best')

export const activateModel = (id: string) =>
  request<{ activated: boolean; adapter_path: string }>(
    `/finetuning/runs/${id}/activate`,
    { method: 'POST' },
  )

// ─── Local pipeline ──────────────────────────────────────────────────────────

export const getLocalStatus = () =>
  request<LocalStatus>('/local/status')

export const processLocally = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ job_id: string; status: string }>(
    '/local/process',
    { method: 'POST', body: form },
  )
}

export const getLocalJob = (jobId: string) =>
  request<{ status: string; result?: Record<string, unknown>; error?: string }>(
    `/local/process/${jobId}`,
  )

export const listLocalJobs = () =>
  request<{ jobs: Array<{ job_id: string; status: string }>; total: number }>(
    '/local/jobs',
  )

export const runBenchmark = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ job_id: string; status: string }>(
    '/local/benchmark',
    { method: 'POST', body: form },
  )
}
