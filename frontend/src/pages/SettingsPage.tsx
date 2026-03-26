import { useState, useEffect } from 'react'
import { Settings, Bell, Shield, Palette, Monitor, Save, RefreshCw, Moon, Sun, User, Globe, Layers } from 'lucide-react'
import { type ExperienceTier, getStoredTier, setStoredTier } from '../components/Layout'

interface Prefs {
  theme: 'light' | 'dark' | 'system'
  notifications: boolean
  autoRefresh: boolean
  refreshInterval: number
  compactMode: boolean
  language: string
}

const defaultPrefs: Prefs = {
  theme: 'light',
  notifications: true,
  autoRefresh: true,
  refreshInterval: 30,
  compactMode: false,
  language: 'en',
}

export function SettingsPage() {
  const [prefs, setPrefs] = useState<Prefs>(defaultPrefs)
  const [saved, setSaved] = useState(false)
  const [tier, setTier] = useState<ExperienceTier>(getStoredTier)

  useEffect(() => {
    try {
      const stored = localStorage.getItem('dealframe_prefs')
      if (stored) setPrefs({ ...defaultPrefs, ...JSON.parse(stored) })
    } catch { /* ignore */ }
  }, [])

  const update = <K extends keyof Prefs>(key: K, val: Prefs[K]) => {
    setPrefs(p => ({ ...p, [key]: val }))
    setSaved(false)
  }

  const handleSave = () => {
    localStorage.setItem('dealframe_prefs', JSON.stringify(prefs))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const Section = ({ title, icon: Icon, children }: { title: string; icon: typeof Settings; children: React.ReactNode }) => (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5 pb-3 border-b border-slate-100">
        <Icon className="w-4.5 h-4.5 text-indigo-500" />
        <h2 className="text-sm font-bold text-slate-700">{title}</h2>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  )

  const Toggle = ({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (v: boolean) => void }) => (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-slate-700">{label}</p>
        <p className="text-xs text-slate-400">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5.5 rounded-full transition ${checked ? 'bg-indigo-600' : 'bg-slate-300'}`}
      >
        <div className={`absolute top-0.5 w-4.5 h-4.5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-slate-600 via-slate-700 to-gray-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-slate-900/20">
        <div className="relative flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-slate-300 animate-pulse" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-widest">Preferences</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Settings</h1>
            <p className="text-slate-400 text-sm mt-1">Customize your DealFrame experience</p>
          </div>
          <button
            onClick={handleSave}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-bold rounded-xl transition shadow-sm ${saved ? 'bg-emerald-500 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
          >
            {saved ? <RefreshCw className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
            {saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Appearance */}
        <Section title="Appearance" icon={Palette}>
          <div>
            <p className="text-sm font-medium text-slate-700 mb-2">Theme</p>
            <div className="flex items-center gap-2">
              {(['light', 'dark', 'system'] as const).map(t => {
                const Icon = t === 'light' ? Sun : t === 'dark' ? Moon : Monitor
                return (
                  <button
                    key={t}
                    onClick={() => update('theme', t)}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition ${prefs.theme === t ? 'bg-indigo-100 text-indigo-700 border border-indigo-200' : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'}`}
                  >
                    <Icon className="w-4 h-4" /> {t.charAt(0).toUpperCase() + t.slice(1)}
                  </button>
                )
              })}
            </div>
          </div>
          <Toggle label="Compact Mode" description="Reduce spacing for denser layouts" checked={prefs.compactMode} onChange={v => update('compactMode', v)} />
        </Section>

        {/* Notifications */}
        <Section title="Notifications" icon={Bell}>
          <Toggle label="Enable Notifications" description="Receive alerts for completed jobs and risks" checked={prefs.notifications} onChange={v => update('notifications', v)} />
        </Section>

        {/* Data & Refresh */}
        <Section title="Data & Refresh" icon={RefreshCw}>
          <Toggle label="Auto-Refresh" description="Automatically refresh dashboard data" checked={prefs.autoRefresh} onChange={v => update('autoRefresh', v)} />
          <div>
            <p className="text-sm font-medium text-slate-700 mb-1">Refresh Interval</p>
            <p className="text-xs text-slate-400 mb-2">How often to refresh (seconds)</p>
            <input
              type="range"
              min={10}
              max={120}
              step={5}
              value={prefs.refreshInterval}
              onChange={e => update('refreshInterval', Number(e.target.value))}
              className="w-full accent-indigo-600"
            />
            <p className="text-xs text-slate-500 text-right">{prefs.refreshInterval}s</p>
          </div>
        </Section>

        {/* Locale */}
        <Section title="Locale" icon={Globe}>
          <div>
            <p className="text-sm font-medium text-slate-700 mb-1">Language</p>
            <select
              value={prefs.language}
              onChange={e => update('language', e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-200 text-sm w-full shadow-sm"
            >
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="de">Deutsch</option>
              <option value="fr">Français</option>
              <option value="ja">日本語</option>
            </select>
          </div>
        </Section>

        {/* Experience Tier */}
        <Section title="Experience Tier" icon={Layers}>
          <p className="text-xs text-slate-400 -mt-2 mb-3">Control how many features appear in the sidebar. You can always change this later.</p>
          {([
            { value: 'essentials' as ExperienceTier, label: 'Essentials', desc: 'Dashboard, Upload, Search, Settings — clean and focused' },
            { value: 'pro' as ExperienceTier, label: 'Pro', desc: 'Analytics, Coaching, Meeting Prep, Copilot, Batch, and more' },
            { value: 'power' as ExperienceTier, label: 'Power', desc: 'Everything — Fine-tuning, Observability, Admin, Schema Builder, etc.' },
          ]).map(opt => (
            <button
              key={opt.value}
              onClick={() => { setTier(opt.value); setStoredTier(opt.value) }}
              className={`w-full text-left px-4 py-3 rounded-lg border transition ${
                tier === opt.value
                  ? 'border-indigo-300 bg-indigo-50 ring-1 ring-indigo-200'
                  : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
              }`}
            >
              <p className={`text-sm font-semibold ${tier === opt.value ? 'text-indigo-700' : 'text-slate-700'}`}>{opt.label}</p>
              <p className="text-xs text-slate-400 mt-0.5">{opt.desc}</p>
            </button>
          ))}
        </Section>
      </div>
    </div>
  )
}
