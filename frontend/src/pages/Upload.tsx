import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileVideo, CheckCircle2, XCircle, Loader2, X, Clapperboard, Zap, Cloud, Link2, Globe } from 'lucide-react'
import { processVideo, processVideoUrl, processLocally, getJob, getLocalJob, listSchemas } from '../api/client'
import { JobProgress } from '../components/JobProgress'

type Mode = 'api' | 'local'
type InputMode = 'file' | 'url'
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

const URL_PIPELINE_STAGES = [
  'Downloading video',
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
  const [inputMode, setInputMode] = useState<InputMode>('url')
  const [isDragging, setIsDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState('')
  const [mode, setMode] = useState<Mode>('api')
  const [useVision, setUseVision] = useState(false)
  const [vertical, setVertical] = useState('')
  const [schemaId, setSchemaId] = useState('')
  const [schemas, setSchemas] = useState<Array<{ schema_id: string; name: string }>>([])
  const [stages, setStages] = useState<Stage[]>(
    PIPELINE_STAGES.map(name => ({ name, status: 'idle' })),
  )
  const [jobId, setJobId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listSchemas().then(d => setSchemas(d.schemas ?? [])).catch(() => {})
  }, [])

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

  const hasInput = inputMode === 'file' ? !!file : videoUrl.trim().length > 0

  const handleSubmit = async () => {
    if (!hasInput) return
    const stageNames = inputMode === 'url' ? URL_PIPELINE_STAGES : PIPELINE_STAGES
    setRunStatus('running')
    setErrorMsg('')
    setStages(stageNames.map(name => ({ name, status: 'idle' })))

    try {
      setStageStatus(0, 'active')

      let res: { job_id: string; status: string }
      if (inputMode === 'url') {
        res = await processVideoUrl(videoUrl.trim(), useVision)
      } else if (mode === 'local') {
        res = await processLocally(file!)
      } else {
        res = await processVideo(file!, useVision)
      }

      const id = res.job_id
      setJobId(id)
      setStageStatus(0, 'done')

      // For API pipeline + URL uploads the durable worker will emit SSE events
      // that the JobProgress card renders in real time. We still poll the job
      // record so we know when to mark "done" for the CTA button.
      const poll = mode === 'local' && inputMode === 'file'
        ? () => getLocalJob(id)
        : () => getJob(id)

      while (true) {
        await new Promise(r => setTimeout(r, 1500))
        const j = await poll()
        if (j.status === 'completed') {
          setStages(stageNames.map(name => ({ name, status: 'done' })))
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
    <div className="p-4 sm:p-6 lg:p-8 max-w-2xl animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
            <Clapperboard className="w-4 h-4 text-indigo-600" />
          </div>
          <h1 className="page-title">Upload & Process</h1>
        </div>
        <p className="page-subtitle">Analyze a sales call, demo, or walkthrough video for decision signals</p>
      </div>

      {/* Input mode toggle */}
      <div className="flex gap-2 mb-5">
        <button
          onClick={() => { setInputMode('url'); setRunStatus('idle'); setErrorMsg('') }}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            inputMode === 'url'
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200'
              : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          <Globe className="w-4 h-4" />
          YouTube / URL
        </button>
        <button
          onClick={() => { setInputMode('file'); setRunStatus('idle'); setErrorMsg('') }}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            inputMode === 'file'
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200'
              : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          <UploadIcon className="w-4 h-4" />
          File Upload
        </button>
      </div>

      {/* URL Input */}
      {inputMode === 'url' && (
        <div className="bg-white border-2 border-slate-200 rounded-2xl p-6 hover:border-indigo-300 transition-colors focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-red-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </div>
            <div>
              <p className="font-bold text-slate-800 text-sm">Paste a YouTube or video URL</p>
              <p className="text-xs text-slate-400 mt-0.5">Supports YouTube, Vimeo, Loom, and 1000+ sites</p>
            </div>
          </div>
          <div className="relative">
            <Link2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="url"
              placeholder="https://youtube.com/watch?v=..."
              value={videoUrl}
              onChange={e => { setVideoUrl(e.target.value); setErrorMsg('') }}
              className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl text-sm bg-slate-50 focus:bg-white focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 outline-none transition-all placeholder:text-slate-300"
            />
          </div>
          {videoUrl && (
            <button
              onClick={() => { setVideoUrl(''); setRunStatus('idle') }}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-500 transition-colors mt-2 px-1"
            >
              <X className="w-3 h-3" /> Clear URL
            </button>
          )}
        </div>
      )}

      {/* File Drop zone */}
      {inputMode === 'file' && (
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          className={`relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200 outline-none focus:ring-2 focus:ring-indigo-300 ${
            isDragging
              ? 'border-indigo-400 bg-indigo-50 scale-[1.01] shadow-md shadow-indigo-100'
              : file
              ? 'border-emerald-300 bg-emerald-50/60'
              : 'border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/30 bg-white'
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
            <div className="flex flex-col items-center gap-3">
              <div className="w-16 h-16 bg-emerald-100 rounded-2xl flex items-center justify-center">
                <FileVideo className="w-8 h-8 text-emerald-600" />
              </div>
              <div>
                <p className="font-bold text-slate-900">{file.name}</p>
                <p className="text-sm text-slate-500 mt-0.5">{formatSize(file.size)}</p>
              </div>
              <button
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-500 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-50"
                onClick={e => { e.stopPropagation(); setFile(null); setRunStatus('idle') }}
              >
                <X className="w-3.5 h-3.5" /> Remove file
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${isDragging ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                <UploadIcon className={`w-8 h-8 transition-colors ${isDragging ? 'text-indigo-500' : 'text-slate-400'}`} />
              </div>
              <div>
                <p className="font-bold text-slate-700">{isDragging ? 'Drop to upload' : 'Drop video here or click to browse'}</p>
                <p className="text-sm text-slate-400 mt-1">MP4, WebM, MOV, MKV, AVI — up to 500 MB</p>
              </div>
            </div>
          )}
        </div>
      )}

      {errorMsg && !hasInput && (
        <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          {errorMsg}
        </div>
      )}

      {/* Processing mode — only show for file uploads */}
      {hasInput && (
        <>
          {inputMode === 'file' && (
            <div className="mt-6">
              <p className="text-sm font-bold text-slate-700 mb-3">Processing mode</p>
              <div className="flex gap-3">
                {(
                  [
                    ['api', 'API Pipeline', 'GPT-4o / Claude extraction', Cloud] as const,
                    ['local', 'Local Pipeline', 'Zero API calls · rule-based', Zap] as const,
                  ]
                ).map(([v, label, sub, Icon]) => (
                  <button
                    key={v}
                    onClick={() => setMode(v)}
                    className={`flex-1 border rounded-2xl px-4 py-4 text-left transition-all duration-150 ${
                      mode === v
                        ? 'border-indigo-400 bg-indigo-50 ring-2 ring-indigo-100 shadow-sm'
                        : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 mb-1">
                      <Icon className={`w-4 h-4 ${mode === v ? 'text-indigo-600' : 'text-slate-400'}`} />
                      <p className={`text-sm font-bold ${mode === v ? 'text-indigo-700' : 'text-slate-800'}`}>
                        {label}
                      </p>
                    </div>
                    <p className="text-xs text-slate-400 ml-6.5">{sub}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {(inputMode === 'url' || mode === 'api') && (
            <label className="flex items-center gap-3 mt-4 cursor-pointer group bg-white border border-slate-200 rounded-xl px-4 py-3 hover:border-slate-300 transition-colors">
              <input
                type="checkbox"
                checked={useVision}
                onChange={e => setUseVision(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <span className="text-sm font-semibold text-slate-700">Enable vision analysis</span>
                <p className="text-xs text-slate-400">Qwen-VL / GPT-4o Vision — analyzes slide content</p>
              </div>
            </label>
          )}

          {runStatus === 'idle' && (
            <>
              {/* Vertical + Schema selectors */}
              <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Vertical</label>
                  <select
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white"
                    value={vertical}
                    onChange={e => setVertical(e.target.value)}
                  >
                    <option value="">— Default —</option>
                    <option value="sales">Sales</option>
                    <option value="procurement">Procurement</option>
                    <option value="ux_research">UX Research</option>
                    <option value="customer_success">Customer Success</option>
                    <option value="real_estate">Real Estate</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Schema</label>
                  <select
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white"
                    value={schemaId}
                    onChange={e => setSchemaId(e.target.value)}
                  >
                    <option value="">— Default —</option>
                    {schemas.map(s => (
                      <option key={s.schema_id} value={s.schema_id}>{s.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <button
                onClick={handleSubmit}
                className="mt-6 w-full btn-primary py-3.5 text-base font-bold shadow-md shadow-indigo-100"
              >
                {inputMode === 'url' ? 'Process URL' : 'Start Processing'}
              </button>
            </>
          )}
        </>
      )}

      {/* Live SSE progress (API pipeline / URL mode only) */}
      {runStatus !== 'idle' && jobId && !(mode === 'local' && inputMode === 'file') && (
        <div className="mt-6">
          <JobProgress jobId={jobId} onComplete={() => setRunStatus('done')} />
          {runStatus === 'done' && jobId && (
            <button
              onClick={() => navigate(`/results/${jobId}`)}
              className="mt-4 w-full btn-primary py-3 text-base font-bold"
            >
              View Results
            </button>
          )}
          {runStatus === 'error' && errorMsg && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-2">
              <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{errorMsg}</p>
            </div>
          )}
        </div>
      )}

      {/* Legacy fallback for local pipeline (no SSE events) */}
      {runStatus !== 'idle' && (!jobId || (mode === 'local' && inputMode === 'file')) && (
        <div className="mt-6 border border-slate-200 rounded-2xl p-6 bg-white shadow-sm">
          <p className="text-sm font-bold text-slate-800 mb-5">Pipeline progress</p>
          <div className="space-y-4">
            {stages.map((stage, idx) => (
              <div key={stage.name} className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  {stage.status === 'done' && (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                  )}
                  {stage.status === 'active' && (
                    <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />
                  )}
                  {stage.status === 'error' && (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                  {stage.status === 'idle' && (
                    <div className="w-5 h-5 rounded-full border-2 border-slate-200 flex items-center justify-center">
                      <span className="text-[9px] font-bold text-slate-300">{idx + 1}</span>
                    </div>
                  )}
                </div>
                <span
                  className={`text-sm font-medium transition-colors ${
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
                {stage.status === 'done' && (
                  <span className="ml-auto text-xs text-emerald-500 font-medium">Done</span>
                )}
              </div>
            ))}
          </div>

          {runStatus === 'done' && jobId && (
            <button
              onClick={() => navigate(`/results/${jobId}`)}
              className="mt-6 w-full btn-primary py-3 text-base font-bold"
            >
              View Results
            </button>
          )}

          {runStatus === 'error' && errorMsg && (
            <div className="mt-5 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-2">
              <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{errorMsg}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
