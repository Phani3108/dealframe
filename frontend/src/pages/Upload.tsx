import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileVideo, CheckCircle2, XCircle, Loader2, X } from 'lucide-react'
import { processVideo, processLocally, getJob, getLocalJob } from '../api/client'

type Mode = 'api' | 'local'
type StageStatus = 'idle' | 'active' | 'done' | 'error'

interface Stage {
  name: string
  status: StageStatus
}

const PIPELINE_STAGES = [
  'Uploading file',
  'Extracting frames',
  'Transcribing audio',
  'Aligning timeline',
  'Extracting intelligence',
]

const SUPPORTED = ['mp4', 'webm', 'mov', 'mkv', 'avi']

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function Upload() {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<Mode>('api')
  const [useVision, setUseVision] = useState(false)
  const [stages, setStages] = useState<Stage[]>(
    PIPELINE_STAGES.map(name => ({ name, status: 'idle' })),
  )
  const [jobId, setJobId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
    if (!SUPPORTED.includes(ext)) {
      setErrorMsg(`Unsupported format ".${ext}". Use: ${SUPPORTED.join(', ')}`)
      return
    }
    setFile(f)
    setRunStatus('idle')
    setErrorMsg('')
    setStages(PIPELINE_STAGES.map(name => ({ name, status: 'idle' })))
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [])

  const setStageStatus = (idx: number, status: StageStatus) => {
    setStages(prev => prev.map((s, i) => (i === idx ? { ...s, status } : s)))
  }

  const handleSubmit = async () => {
    if (!file) return
    setRunStatus('running')
    setErrorMsg('')
    setStages(PIPELINE_STAGES.map(name => ({ name, status: 'idle' })))

    try {
      setStageStatus(0, 'active')
      const res = mode === 'local'
        ? await processLocally(file)
        : await processVideo(file, useVision)
      const id = res.job_id
      setJobId(id)
      setStageStatus(0, 'done')

      // Animate through stages while polling
      let stageIdx = 1
      const poll = mode === 'local'
        ? () => getLocalJob(id)
        : () => getJob(id)

      setStageStatus(stageIdx, 'active')
      while (true) {
        await new Promise(r => setTimeout(r, 1800))
        const j = await poll()

        // Advance visual stage
        if (stageIdx < PIPELINE_STAGES.length - 1) {
          setStageStatus(stageIdx, 'done')
          stageIdx++
          setStageStatus(stageIdx, 'active')
        }

        if (j.status === 'completed') {
          setStages(PIPELINE_STAGES.map(name => ({ name, status: 'done' })))
          setRunStatus('done')
          break
        } else if (j.status === 'failed') {
          throw new Error((j as { error?: string }).error ?? 'Processing failed')
        }
      }
    } catch (e) {
      setRunStatus('error')
      setErrorMsg(e instanceof Error ? e.message : String(e))
      setStages(prev =>
        prev.map(s => s.status === 'active' ? { ...s, status: 'error' } : s),
      )
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="page-header">
        <h1 className="page-title">Upload & Process</h1>
        <p className="page-subtitle">Analyze a sales call, demo, or walkthrough video</p>
      </div>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={`relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all outline-none focus:ring-2 focus:ring-indigo-300 ${
          isDragging
            ? 'border-indigo-400 bg-indigo-50 scale-[1.01]'
            : file
            ? 'border-emerald-300 bg-emerald-50'
            : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileVideo className="w-12 h-12 text-emerald-500" />
            <p className="font-semibold text-slate-900">{file.name}</p>
            <p className="text-sm text-slate-500">{formatSize(file.size)}</p>
            <button
              className="mt-1 text-xs text-slate-400 hover:text-red-500 flex items-center gap-1"
              onClick={e => { e.stopPropagation(); setFile(null); setRunStatus('idle') }}
            >
              <X className="w-3 h-3" /> Remove
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-1">
              <UploadIcon className="w-7 h-7 text-slate-400" />
            </div>
            <p className="font-semibold text-slate-700">Drop video here or click to browse</p>
            <p className="text-sm text-slate-400">MP4, WebM, MOV, MKV — up to 500 MB</p>
          </div>
        )}
      </div>

      {errorMsg && !file && (
        <p className="mt-2 text-sm text-red-600">{errorMsg}</p>
      )}

      {/* Processing mode */}
      {file && (
        <>
          <div className="mt-6">
            <p className="text-sm font-semibold text-slate-700 mb-3">Processing mode</p>
            <div className="flex gap-3">
              {(
                [
                  ['api', 'API Pipeline', 'GPT-4o / Claude extraction'] as const,
                  ['local', 'Local Pipeline', 'Zero API calls · rule-based'] as const,
                ]
              ).map(([v, label, sub]) => (
                <button
                  key={v}
                  onClick={() => setMode(v)}
                  className={`flex-1 border rounded-xl px-4 py-3 text-left transition-colors ${
                    mode === v
                      ? 'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-200'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <p className={`text-sm font-semibold ${mode === v ? 'text-indigo-700' : 'text-slate-800'}`}>
                    {label}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">{sub}</p>
                </button>
              ))}
            </div>

            {mode === 'api' && (
              <label className="flex items-center gap-2.5 mt-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={useVision}
                  onChange={e => setUseVision(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-slate-600 group-hover:text-slate-800">
                  Enable vision analysis (Qwen-VL / GPT-4o Vision)
                </span>
              </label>
            )}
          </div>

          {runStatus === 'idle' && (
            <button
              onClick={handleSubmit}
              className="mt-6 w-full btn-primary py-3 text-base"
            >
              Start Processing
            </button>
          )}
        </>
      )}

      {/* Progress tracker */}
      {runStatus !== 'idle' && (
        <div className="mt-6 border border-slate-200 rounded-xl p-5 bg-white">
          <p className="text-sm font-semibold text-slate-700 mb-5">Pipeline progress</p>
          <div className="space-y-3.5">
            {stages.map(stage => (
              <div key={stage.name} className="flex items-center gap-3">
                {stage.status === 'done' && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                )}
                {stage.status === 'active' && (
                  <Loader2 className="w-4 h-4 text-indigo-500 animate-spin flex-shrink-0" />
                )}
                {stage.status === 'error' && (
                  <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                )}
                {stage.status === 'idle' && (
                  <div className="w-4 h-4 rounded-full border-2 border-slate-200 flex-shrink-0" />
                )}
                <span
                  className={`text-sm transition-colors ${
                    stage.status === 'active'
                      ? 'text-indigo-600 font-semibold'
                      : stage.status === 'done'
                      ? 'text-slate-700'
                      : stage.status === 'error'
                      ? 'text-red-600'
                      : 'text-slate-400'
                  }`}
                >
                  {stage.name}
                </span>
              </div>
            ))}
          </div>

          {runStatus === 'done' && jobId && (
            <button
              onClick={() => navigate(`/results/${jobId}`)}
              className="mt-5 w-full btn-primary py-2.5"
            >
              View Results →
            </button>
          )}

          {runStatus === 'error' && errorMsg && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              <p className="text-sm text-red-700">{errorMsg}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
