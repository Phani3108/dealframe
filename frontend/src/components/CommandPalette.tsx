import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, CornerDownLeft, X, Inbox, Upload, BarChart3, MessageSquare, Brain, Zap, RefreshCw, Radio, Bot, ShieldCheck, Settings, Cpu, Layers, Calendar, Home, LayoutDashboard, GitCompare } from 'lucide-react'
import { searchSegments, listDeals, type DealRow } from '../api/client'

type CommandItem = {
  id: string
  label: string
  section: string
  icon: typeof Search
  action: () => void
  keywords?: string
}

const NAV_ITEMS: Array<Omit<CommandItem, 'action'> & { path: string }> = [
  { id: 'nav-home', label: 'Home', section: 'Navigate', icon: Home, path: '/home' },
  { id: 'nav-deals', label: 'Deal Inbox', section: 'Navigate', icon: Inbox, path: '/deals' },
  { id: 'nav-dashboard', label: 'Dashboard', section: 'Navigate', icon: LayoutDashboard, path: '/dashboard' },
  { id: 'nav-upload', label: 'Upload & Process', section: 'Navigate', icon: Upload, path: '/upload' },
  { id: 'nav-intelligence', label: 'Analytics', section: 'Navigate', icon: Brain, path: '/intelligence' },
  { id: 'nav-compare', label: 'Deal Compare', section: 'Navigate', icon: GitCompare, path: '/compare' },
  { id: 'nav-chat', label: 'Ask Library', section: 'Navigate', icon: MessageSquare, path: '/chat' },
  { id: 'nav-copilot', label: 'Live Copilot', section: 'Navigate', icon: Bot, path: '/copilot' },
  { id: 'nav-meeting', label: 'Meeting Prep', section: 'Navigate', icon: Calendar, path: '/meeting-prep' },
  { id: 'nav-batch', label: 'Batch', section: 'Navigate', icon: Layers, path: '/batch' },
  { id: 'nav-streaming', label: 'Live Stream', section: 'Navigate', icon: Radio, path: '/streaming' },
  { id: 'nav-finetuning', label: 'Fine-tuning', section: 'Navigate', icon: Zap, path: '/finetuning' },
  { id: 'nav-flywheel', label: 'Flywheel', section: 'Navigate', icon: RefreshCw, path: '/flywheel' },
  { id: 'nav-verticals', label: 'Vertical Packs', section: 'Navigate', icon: Layers, path: '/verticals' },
  { id: 'nav-local', label: 'Local Pipeline', section: 'Navigate', icon: Cpu, path: '/local' },
  { id: 'nav-observability', label: 'Observability', section: 'Navigate', icon: BarChart3, path: '/observability' },
  { id: 'nav-admin', label: 'Admin', section: 'Navigate', icon: ShieldCheck, path: '/admin' },
  { id: 'nav-settings', label: 'Settings', section: 'Navigate', icon: Settings, path: '/settings' },
]

export function CommandPalette() {
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const [remoteResults, setRemoteResults] = useState<Array<CommandItem>>([])
  const [recentDeals, setRecentDeals] = useState<DealRow[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(o => !o)
        return
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setSelected(0)
    setTimeout(() => inputRef.current?.focus(), 50)
    listDeals(10).then(r => setRecentDeals(r.deals)).catch(() => setRecentDeals([]))
  }, [open])

  useEffect(() => {
    if (!open) return
    const q = query.trim()
    if (q.length < 2) { setRemoteResults([]); return }
    let cancelled = false
    const t = setTimeout(async () => {
      try {
        const res = await searchSegments(q, undefined, undefined, 8)
        if (cancelled) return
        const results = (res.results ?? []).map((r, i) => ({
          id: `lib-${i}-${r.doc_id}`,
          label: `${r.timestamp_str}  ·  ${r.transcript_snippet.slice(0, 80)}`,
          section: 'Library search',
          icon: Search,
          action: () => { if (r.video_id) nav(`/results/${r.video_id}`) },
          keywords: q,
        }) as CommandItem)
        setRemoteResults(results)
      } catch { setRemoteResults([]) }
    }, 250)
    return () => { cancelled = true; clearTimeout(t) }
  }, [query, open, nav])

  const items = useMemo<CommandItem[]>(() => {
    const q = query.trim().toLowerCase()
    const navItems: CommandItem[] = NAV_ITEMS
      .filter(n => !q || n.label.toLowerCase().includes(q))
      .map(n => ({ id: n.id, label: n.label, section: n.section, icon: n.icon, action: () => nav(n.path) }))

    const dealItems: CommandItem[] = recentDeals
      .filter(d => !q || d.title.toLowerCase().includes(q) || d.job_id.toLowerCase().includes(q) || (d.top_topic ?? '').toLowerCase().includes(q))
      .slice(0, 6)
      .map(d => ({
        id: `deal-${d.job_id}`,
        label: d.title,
        section: 'Deals',
        icon: Inbox,
        action: () => nav(`/results/${d.job_id}`),
      }))

    return [...dealItems, ...navItems, ...remoteResults]
  }, [query, recentDeals, remoteResults, nav])

  const grouped = useMemo(() => {
    const map = new Map<string, CommandItem[]>()
    items.forEach(it => {
      if (!map.has(it.section)) map.set(it.section, [])
      map.get(it.section)!.push(it)
    })
    return map
  }, [items])

  useEffect(() => { setSelected(0) }, [query, items.length])

  if (!open) return null

  const flat = items
  const run = (idx: number) => {
    const item = flat[idx]
    if (!item) return
    item.action()
    setOpen(false)
  }

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, flat.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); run(selected) }
  }

  return (
    <div
      className="fixed inset-0 z-[100] bg-slate-900/40 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 border-b border-slate-100">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Search deals, navigate, ask the library…"
            className="flex-1 py-4 bg-transparent outline-none text-sm"
          />
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto py-2">
          {flat.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-400">No matches.</p>
          ) : (
            Array.from(grouped.entries()).map(([section, its]) => (
              <div key={section} className="mb-1">
                <p className="px-4 pt-3 pb-1 text-[10px] uppercase tracking-wider font-bold text-slate-400">{section}</p>
                {its.map(it => {
                  const idx = flat.findIndex(f => f.id === it.id)
                  const active = idx === selected
                  const Icon = it.icon
                  return (
                    <button
                      key={it.id}
                      onMouseEnter={() => setSelected(idx)}
                      onClick={() => run(idx)}
                      className={`w-full flex items-center gap-3 px-4 py-2 text-left text-sm ${
                        active ? 'bg-indigo-50 text-indigo-900' : 'text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      <Icon className="w-4 h-4 text-slate-400" />
                      <span className="flex-1 truncate">{it.label}</span>
                      {active && <CornerDownLeft className="w-3.5 h-3.5 text-slate-400" />}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50 text-[10px] text-slate-500 flex items-center gap-3">
          <span><kbd className="font-mono px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px]">↑↓</kbd> Navigate</span>
          <span><kbd className="font-mono px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px]">↵</kbd> Select</span>
          <span><kbd className="font-mono px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px]">esc</kbd> Close</span>
          <span className="ml-auto font-medium">⌘K to toggle</span>
        </div>
      </div>
    </div>
  )
}
