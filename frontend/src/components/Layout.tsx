import { useState, useEffect, useMemo } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  Eye,
  Brain,
  Zap,
  Cpu,
  Activity,
  BarChart3,
  Search,
  Radio,
  MessageSquare,
  Target,
  Layers,
  Calendar,
  Network,
  Settings,
  Plug,
  MessageSquareText,
  ListChecks,
  Shield,
  GitCompare,
  TrendingUp,
  Bot,
  ShieldCheck,
  Bell,
  ChevronRight,
  Menu,
  X,
  Home,
  Inbox,
  RefreshCw,
} from 'lucide-react'
import { getNotifications, markAllNotificationsRead } from '../api/client'

export type ExperienceTier = 'essentials' | 'pro' | 'power'

/** Each nav item declares the minimum tier required to display it. */
interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  tier: ExperienceTier
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    label: 'Core',
    items: [
      { to: '/home', label: 'Home', icon: Home, tier: 'essentials' },
      { to: '/deals', label: 'Deal Inbox', icon: Inbox, tier: 'essentials' },
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, tier: 'essentials' },
      { to: '/upload', label: 'Upload & Process', icon: Upload, tier: 'essentials' },
      { to: '/search', label: 'Search', icon: Search, tier: 'essentials' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/intelligence', label: 'Analytics', icon: Brain, tier: 'pro' },
      { to: '/coaching', label: 'Coaching', icon: Target, tier: 'pro' },
      { to: '/chat', label: 'Ask Library', icon: MessageSquare, tier: 'pro' },
      { to: '/copilot', label: 'Live Copilot', icon: Bot, tier: 'pro' },
      { to: '/meeting-prep', label: 'Meeting Prep', icon: Calendar, tier: 'pro' },
      { to: '/batch', label: 'Batch', icon: Layers, tier: 'pro' },
      { to: '/patterns', label: 'Pattern Miner', icon: TrendingUp, tier: 'power' },
      { to: '/compare', label: 'Deal Compare', icon: GitCompare, tier: 'pro' },
      { to: '/diff', label: 'Diff Engine', icon: GitCompare, tier: 'power' },
      { to: '/knowledge-graph', label: 'Knowledge Graph', icon: Network, tier: 'power' },
    ],
  },
  {
    label: 'Models',
    items: [
      { to: '/observatory', label: 'Observatory', icon: Eye, tier: 'power' },
      { to: '/finetuning', label: 'Fine-tuning', icon: Zap, tier: 'power' },
      { to: '/flywheel', label: 'Flywheel', icon: RefreshCw, tier: 'power' },
      { to: '/local', label: 'Local Pipeline', icon: Cpu, tier: 'power' },
      { to: '/streaming', label: 'Live Stream', icon: Radio, tier: 'power' },
      { to: '/schema-builder', label: 'Schema Builder', icon: Settings, tier: 'power' },
      { to: '/verticals', label: 'Vertical Packs', icon: Layers, tier: 'pro' },
    ],
  },
  {
    label: 'Platform',
    items: [
      { to: '/integrations', label: 'Connections', icon: Plug, tier: 'pro' },
      { to: '/observability', label: 'Observability', icon: BarChart3, tier: 'power' },
      { to: '/annotations', label: 'Annotations', icon: MessageSquareText, tier: 'power' },
      { to: '/review-queue', label: 'Review Queue', icon: ListChecks, tier: 'power' },
      { to: '/audit-log', label: 'Audit Log', icon: Shield, tier: 'power' },
      { to: '/admin', label: 'Admin', icon: ShieldCheck, tier: 'power' },
      { to: '/settings', label: 'Settings', icon: Settings, tier: 'essentials' },
    ],
  },
]

const TIER_ORDER: Record<ExperienceTier, number> = { essentials: 0, pro: 1, power: 2 }

export function getStoredTier(): ExperienceTier {
  try {
    const stored = localStorage.getItem('dealframe_tier')
    if (stored && stored in TIER_ORDER) return stored as ExperienceTier
  } catch { /* SSR-safe */ }
  return 'essentials'
}

export function setStoredTier(tier: ExperienceTier) {
  try { localStorage.setItem('dealframe_tier', tier) } catch { /* SSR-safe */ }
}

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [tier, setTier] = useState<ExperienceTier>(getStoredTier)
  const [unread, setUnread] = useState(0)
  const [showNotifs, setShowNotifs] = useState(false)
  const [notifs, setNotifs] = useState<Array<{ id: string; type: string; title: string; message: string; read: boolean; created_at: number }>>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  // Close sidebar on navigation (mobile)
  useEffect(() => { setSidebarOpen(false) }, [location.pathname])

  // Close sidebar on Escape key
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSidebarOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Prevent body scroll when sidebar overlay is open on mobile
  useEffect(() => {
    if (sidebarOpen) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [sidebarOpen])

  // Listen for tier changes from Settings page
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'dealframe_tier') setTier(getStoredTier())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Also poll localStorage so same-tab changes from Settings are picked up
  useEffect(() => {
    const iv = setInterval(() => {
      const current = getStoredTier()
      setTier(prev => prev !== current ? current : prev)
    }, 500)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    getNotifications('default', true)
      .then(r => { setUnread(r.unread_count ?? 0); setNotifs(r.notifications ?? []) })
      .catch(() => {})
    const iv = setInterval(() => {
      getNotifications('default', true)
        .then(r => { setUnread(r.unread_count ?? 0); setNotifs(r.notifications ?? []) })
        .catch(() => {})
    }, 30000)
    return () => clearInterval(iv)
  }, [])

  const handleMarkAll = async () => {
    await markAllNotificationsRead('default').catch(() => {})
    setUnread(0)
    setNotifs([])
  }

  /** Filter nav groups to only show items at or below the current tier. */
  const filteredGroups = useMemo(() => {
    const threshold = TIER_ORDER[tier]
    return navGroups
      .map(g => ({ ...g, items: g.items.filter(i => TIER_ORDER[i.tier] <= threshold) }))
      .filter(g => g.items.length > 0)
  }, [tier])

  const tierLabel: Record<ExperienceTier, string> = { essentials: 'Essentials', pro: 'Pro', power: 'Power' }

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Dark Sidebar — hidden on mobile by default, overlay when toggled */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-[#0a0f1e] flex flex-col flex-shrink-0
        transform transition-transform duration-300 ease-in-out
        lg:relative lg:translate-x-0 lg:w-60
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo + mobile close */}
        <div className="px-5 py-5 border-b border-white/[0.06]">
          <div className="flex items-center justify-between">
            <NavLink to="/home" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
              <div className="w-9 h-9 bg-gradient-to-br from-indigo-400 via-indigo-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-900/50 flex-shrink-0">
                <Activity className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-bold text-white text-sm leading-tight tracking-tight">DealFrame</p>
                <p className="text-[10px] text-slate-500 leading-tight mt-0.5">Negotiation Intelligence</p>
              </div>
            </NavLink>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 transition-colors"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tier toggle — segmented control */}
        <div className="px-3 pt-4 pb-2">
          <p className="px-2.5 mb-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">Experience</p>
          <div className="flex bg-white/[0.04] rounded-lg p-0.5 border border-white/[0.06]">
            {(['essentials', 'pro', 'power'] as ExperienceTier[]).map(opt => (
              <button
                key={opt}
                onClick={() => { setTier(opt); setStoredTier(opt) }}
                className={`flex-1 text-[11px] font-bold uppercase tracking-wider py-1.5 rounded-md transition-all duration-150 ${
                  tier === opt
                    ? 'bg-indigo-500/20 text-indigo-300 shadow-sm'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'
                }`}
              >
                {tierLabel[opt]}
              </button>
            ))}
          </div>
        </div>

        {/* Nav — filtered by experience tier */}
        <nav className="flex-1 px-3 py-2 overflow-y-auto">
          {filteredGroups.map(({ label, items }) => (
            <div key={label} className="mb-5">
              <p className="px-2.5 mb-1.5 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">
                {label}
              </p>
              <div className="space-y-0.5">
                {items.map(({ to, label: itemLabel, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/dashboard'}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 ${
                        isActive
                          ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/25 shadow-sm'
                          : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                      }`
                    }
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" />
                    {itemLabel}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}

        </nav>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-white/[0.06]">
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500 text-white text-xs font-bold rounded-lg shadow hover:from-indigo-600 hover:to-purple-600 transition-all w-full justify-center"
            style={{ letterSpacing: '0.04em' }}
          >
            <svg width="16" height="16" fill="none" viewBox="0 0 16 16" className="inline-block mr-1"><path d="M10.5 2.5h3v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M6 10l7.5-7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M13.5 8.5v3a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            API Docs
          </a>
          <p className="text-[10px] text-slate-700 mt-1.5">v0.1.0 · 10 Phases</p>
          {/* Copyright — do not remove */}
          <div className="mt-3 pt-3 border-t border-white/[0.04]">
            <p className="text-[9px] text-slate-700 leading-tight">
              © 2024-2026{' '}
              <a
                href="https://linkedin.com/in/phani-marupaka"
                target="_blank"
                rel="noreferrer"
                className="hover:text-indigo-400 transition-colors"
              >
                Phani Marupaka
              </a>
            </p>
            <a
              href="https://phanimarupaka.netlify.app"
              target="_blank"
              rel="noreferrer"
              className="text-[9px] text-slate-700 hover:text-indigo-400 transition-colors"
            >
              phanimarupaka.netlify.app ↗
            </a>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with hamburger + notification bell */}
        <header className="flex items-center justify-between px-4 sm:px-6 py-2.5 border-b border-slate-200 bg-white flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 -ml-1 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="hidden lg:block" />

          {/* Notification bell */}
          <div className="relative">
            <button
              onClick={() => setShowNotifs(!showNotifs)}
              className="relative p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              aria-label="Notifications"
            >
              <Bell className="w-5 h-5" />
              {unread > 0 && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </button>

            {/* Notification dropdown */}
            {showNotifs && (
              <div className="absolute right-0 top-full mt-1 w-80 bg-white border border-slate-200 rounded-xl shadow-xl z-50 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                  <span className="text-sm font-bold text-slate-900">Notifications</span>
                  {unread > 0 && (
                    <button
                      onClick={handleMarkAll}
                      className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                {notifs.length === 0 ? (
                  <div className="px-4 py-8 text-center">
                    <Bell className="w-6 h-6 text-slate-300 mx-auto mb-2" />
                    <p className="text-sm text-slate-400">No notifications</p>
                  </div>
                ) : (
                  <div className="max-h-64 overflow-y-auto divide-y divide-slate-100">
                    {notifs.slice(0, 10).map(n => (
                      <div key={n.id} className={`px-4 py-3 ${!n.read ? 'bg-indigo-50/50' : ''}`}>
                        <p className="text-xs font-semibold text-slate-700">{n.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5 truncate">{n.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </header>

        {/* Scrollable main content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
