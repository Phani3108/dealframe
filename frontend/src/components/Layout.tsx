import { useState, useEffect, useMemo } from 'react'
import { NavLink } from 'react-router-dom'
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
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, tier: 'essentials' },
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
      { to: '/diff', label: 'Diff Engine', icon: GitCompare, tier: 'power' },
      { to: '/knowledge-graph', label: 'Knowledge Graph', icon: Network, tier: 'power' },
    ],
  },
  {
    label: 'Models',
    items: [
      { to: '/observatory', label: 'Observatory', icon: Eye, tier: 'power' },
      { to: '/finetuning', label: 'Fine-tuning', icon: Zap, tier: 'power' },
      { to: '/local', label: 'Local Pipeline', icon: Cpu, tier: 'power' },
      { to: '/streaming', label: 'Live Stream', icon: Radio, tier: 'power' },
      { to: '/schema-builder', label: 'Schema Builder', icon: Settings, tier: 'power' },
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
      {/* Dark Sidebar */}
      <aside className="w-60 bg-[#0a0f1e] flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-indigo-400 via-indigo-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-900/50 flex-shrink-0">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-white text-sm leading-tight tracking-tight">DealFrame</p>
              <p className="text-[10px] text-slate-500 leading-tight mt-0.5">Negotiation Intelligence</p>
            </div>
          </div>
        </div>

        {/* Nav — filtered by experience tier */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
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
                    end={to === '/'}
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

          {/* Tier upgrade prompt */}
          {tier !== 'power' && (
            <NavLink
              to="/settings"
              className="flex items-center gap-2 px-2.5 py-2 mt-2 rounded-lg text-[11px] text-indigo-400/70 hover:text-indigo-300 hover:bg-white/[0.04] transition-all"
            >
              <ChevronRight className="w-3.5 h-3.5" />
              <span>Unlock more in Settings</span>
            </NavLink>
          )}
        </nav>

        {/* Tier badge + Footer */}
        <div className="px-4 py-4 border-t border-white/[0.06]">
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
              tier === 'power' ? 'bg-violet-500/20 text-violet-300' :
              tier === 'pro' ? 'bg-indigo-500/20 text-indigo-300' :
              'bg-slate-500/20 text-slate-400'
            }`}>
              {tierLabel[tier]}
            </span>
          </div>
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-indigo-400 transition-colors w-fit"
          >
            API Docs ↗
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
        {/* Top bar with notification bell */}
        <header className="flex items-center justify-end px-6 py-2.5 border-b border-slate-200 bg-white flex-shrink-0">
          <div className="relative">
            <button
              onClick={() => setShowNotifs(!showNotifs)}
              className="relative p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition"
            >
              <Bell className="w-5 h-5" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </button>
            {showNotifs && (
              <div className="absolute right-0 mt-1 w-80 bg-white rounded-xl border border-slate-200 shadow-lg z-50 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                  <span className="text-sm font-bold text-slate-700">Notifications</span>
                  {unread > 0 && (
                    <button onClick={handleMarkAll} className="text-xs text-indigo-500 hover:text-indigo-700 font-medium transition">Mark all read</button>
                  )}
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {notifs.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-6">All caught up!</p>
                  ) : (
                    notifs.slice(0, 10).map(n => (
                      <div key={n.id} className="px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50/50">
                        <p className="text-xs font-semibold text-slate-700">{n.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </header>
        <main className="flex-1 overflow-auto bg-slate-50">
          {children}
        </main>
      </div>
    </div>
  )
}

