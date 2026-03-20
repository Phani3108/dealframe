import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  Eye,
  Brain,
  Zap,
  Cpu,
  Activity,
} from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload & Process', icon: Upload },
  { to: '/observatory', label: 'Observatory', icon: Eye },
  { to: '/intelligence', label: 'Intelligence', icon: Brain },
  { to: '/finetuning', label: 'Fine-tuning', icon: Zap },
  { to: '/local', label: 'Local Pipeline', icon: Cpu },
]

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen bg-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 border-r border-slate-200 flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shadow-sm">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="font-semibold text-slate-900 text-sm leading-tight">TemporalOS</p>
              <p className="text-xs text-slate-400 leading-tight">Decision Intelligence</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-slate-100">
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors"
          >
            <span>API Docs</span>
            <span className="text-slate-300">→</span>
          </a>
          <p className="text-xs text-slate-300 mt-1">v0.1.0 · Phases 0–6</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-white">
        {children}
      </main>
    </div>
  )
}
