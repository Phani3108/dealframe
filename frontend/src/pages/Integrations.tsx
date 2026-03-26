import { useState, useEffect } from 'react'
import {
  Plug, CheckCircle2, XCircle, ExternalLink, Zap, MessageSquare,
  FileText, TrendingUp, Building, Hash, Loader2, RefreshCw,
} from 'lucide-react'

interface IntegrationStatus {
  configured: boolean
}

interface StatusMap {
  zoom: IntegrationStatus
  teams: IntegrationStatus
  slack: IntegrationStatus
  notion: IntegrationStatus
  salesforce: IntegrationStatus
  hubspot: IntegrationStatus
  google_meet: IntegrationStatus
}

interface Webhook {
  id: string
  url: string
  events: string[]
  active: boolean
  description: string
}

const INTEGRATIONS = [
  {
    key: 'zoom',
    name: 'Zoom',
    icon: '🎥',
    description: 'Auto-ingest recordings when a Zoom meeting ends.',
    docsUrl: '#',
    envVar: 'ZOOM_WEBHOOK_SECRET_TOKEN',
    category: 'video',
  },
  {
    key: 'google_meet',
    name: 'Google Meet',
    icon: '📹',
    description: 'Connect via Google Calendar webhooks to auto-detect recordings.',
    docsUrl: '#',
    envVar: 'GOOGLE_CLIENT_ID',
    category: 'video',
  },
  {
    key: 'teams',
    name: 'Microsoft Teams',
    icon: '💼',
    description: 'Subscribe to Teams call recording events via Microsoft Graph.',
    docsUrl: '#',
    envVar: 'TEAMS_CLIENT_STATE',
    category: 'video',
  },
  {
    key: 'slack',
    name: 'Slack',
    icon: '💬',
    description: 'Slash commands + risk alerts in Slack channels.',
    docsUrl: '#',
    envVar: 'SLACK_SIGNING_SECRET',
    category: 'messaging',
  },
  {
    key: 'notion',
    name: 'Notion',
    icon: '📄',
    description: 'Export video analysis to a Notion database automatically.',
    docsUrl: '#',
    envVar: 'NOTION_INTEGRATION_TOKEN',
    category: 'productivity',
  },
  {
    key: 'salesforce',
    name: 'Salesforce',
    icon: '☁️',
    description: 'Create Activities on Contacts/Opportunities from every call.',
    docsUrl: '#',
    envVar: 'SALESFORCE_ACCESS_TOKEN',
    category: 'crm',
  },
  {
    key: 'hubspot',
    name: 'HubSpot',
    icon: '🧲',
    description: 'Push Note engagements to HubSpot Contacts and Deals.',
    docsUrl: '#',
    envVar: 'HUBSPOT_ACCESS_TOKEN',
    category: 'crm',
  },
]

const WEBHOOK_EVENTS = [
  'job.completed', 'job.failed', 'risk.high_detected', 'batch.completed', 'integration.error',
]

function IntegrationCard({ config, status }: { config: typeof INTEGRATIONS[0]; status?: IntegrationStatus }) {
  const active = status?.configured ?? false
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 flex items-start gap-4">
      <div className="text-2xl">{config.icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-semibold text-slate-900">{config.name}</p>
          {active
            ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            : <XCircle className="w-4 h-4 text-slate-300" />}
        </div>
        <p className="text-sm text-slate-500 mt-0.5">{config.description}</p>
        <p className="text-xs text-slate-400 mt-2 font-mono">Set: {config.envVar}</p>
      </div>
      <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
        active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
      }`}>
        {active ? 'Connected' : 'Not configured'}
      </span>
    </div>
  )
}

export function Integrations() {
  const [statuses, setStatuses] = useState<Partial<StatusMap>>({})
  const [webhooks, setWebhooks] = useState<Webhook[]>([])
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [newUrl, setNewUrl] = useState('')
  const [newEvents, setNewEvents] = useState<string[]>(['job.completed'])
  const [newSecret, setNewSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [zapSub, setZapSub] = useState('')
  const [zapEvent, setZapEvent] = useState('job.completed')

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/integrations/status').then(r => r.json()).catch(() => ({})),
      fetch('/api/v1/webhooks').then(r => r.json()).catch(() => ({ webhooks: [] })),
    ]).then(([s, w]) => {
      setStatuses(s)
      setWebhooks(w.webhooks ?? [])
    }).finally(() => setLoadingStatus(false))
  }, [])

  const saveWebhook = async () => {
    if (!newUrl.trim()) return
    setSaving(true)
    try {
      const r = await fetch('/api/v1/webhooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newUrl, events: newEvents, secret: newSecret }),
      })
      const d = await r.json()
      setWebhooks(prev => [d.webhook, ...prev])
      setNewUrl(''); setNewSecret('')
    } finally {
      setSaving(false)
    }
  }

  const deleteWebhook = async (id: string) => {
    await fetch(`/api/v1/webhooks/${id}`, { method: 'DELETE' })
    setWebhooks(prev => prev.filter(w => w.id !== id))
  }

  const subscribeZapier = async () => {
    if (!zapSub.trim()) return
    const r = await fetch('/api/v1/integrations/zapier/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_url: zapSub, event: zapEvent }),
    })
    if (r.ok) setZapSub('')
  }

  const categories = ['video', 'messaging', 'crm', 'productivity']

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Plug className="w-6 h-6 text-indigo-500" />
          Integrations
        </h1>
        <p className="text-slate-500 mt-1 text-sm">Connect DealFrame to your existing stack.</p>
      </div>

      {/* Integration status */}
      {categories.map(cat => {
        const items = INTEGRATIONS.filter(i => i.category === cat)
        if (!items.length) return null
        return (
          <div key={cat}>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3 capitalize">{cat}</h2>
            <div className="space-y-3">
              {items.map(i => (
                <IntegrationCard
                  key={i.key}
                  config={i}
                  status={statuses[i.key as keyof StatusMap]}
                />
              ))}
            </div>
          </div>
        )
      })}

      {/* Webhooks */}
      <div>
        <h2 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
          <Zap className="w-4 h-4 text-indigo-400" /> Webhooks
        </h2>
        <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
          <div className="space-y-2">
            <input
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm"
              placeholder="https://your-server.com/webhook"
              value={newUrl}
              onChange={e => setNewUrl(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              {WEBHOOK_EVENTS.map(evt => (
                <label key={evt} className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newEvents.includes(evt)}
                    onChange={e => setNewEvents(prev =>
                      e.target.checked ? [...prev, evt] : prev.filter(x => x !== evt)
                    )}
                    className="accent-indigo-600"
                  />
                  {evt}
                </label>
              ))}
            </div>
            <input
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm"
              placeholder="HMAC secret (optional)"
              value={newSecret}
              onChange={e => setNewSecret(e.target.value)}
              type="password"
            />
            <button
              onClick={saveWebhook}
              disabled={saving || !newUrl}
              className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Hash className="w-4 h-4" />}
              Register Webhook
            </button>
          </div>
          {webhooks.length > 0 && (
            <div className="space-y-2 pt-3 border-t border-slate-100">
              {webhooks.map(w => (
                <div key={w.id} className="flex items-center gap-3 text-sm">
                  <CheckCircle2 className={`w-4 h-4 ${w.active ? 'text-emerald-500' : 'text-slate-300'}`} />
                  <span className="font-mono text-slate-600 flex-1 truncate">{w.url}</span>
                  <span className="text-xs text-slate-400">{w.events.length} event{w.events.length !== 1 ? 's' : ''}</span>
                  <button onClick={() => deleteWebhook(w.id)} className="text-red-400 hover:text-red-600 text-xs">Delete</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Zapier */}
      <div>
        <h2 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
          ⚡ Zapier REST Hooks
        </h2>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-4">Subscribe a Zapier hook URL to receive DealFrame events.</p>
          <div className="flex gap-3">
            <input
              className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm"
              placeholder="https://hooks.zapier.com/hooks/catch/…"
              value={zapSub}
              onChange={e => setZapSub(e.target.value)}
            />
            <select
              className="border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white"
              value={zapEvent}
              onChange={e => setZapEvent(e.target.value)}
            >
              {WEBHOOK_EVENTS.map(e => <option key={e} value={e}>{e}</option>)}
            </select>
            <button
              onClick={subscribeZapier}
              disabled={!zapSub}
              className="px-5 py-2.5 bg-orange-500 text-white text-sm rounded-xl hover:bg-orange-600 disabled:opacity-40"
            >
              Subscribe
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
