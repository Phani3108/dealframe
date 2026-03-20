const styles: Record<string, string> = {
  high: 'bg-red-50 text-red-700 border border-red-200 ring-1 ring-red-100',
  medium: 'bg-amber-50 text-amber-700 border border-amber-200 ring-1 ring-amber-100',
  low: 'bg-emerald-50 text-emerald-700 border border-emerald-200 ring-1 ring-emerald-100',
  pending: 'bg-slate-50 text-slate-600 border border-slate-200',
  processing: 'bg-blue-50 text-blue-700 border border-blue-200',
  completed: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  failed: 'bg-red-50 text-red-700 border border-red-200',
  running: 'bg-indigo-50 text-indigo-700 border border-indigo-200',
}

interface BadgeProps {
  label: string
  className?: string
}

export function Badge({ label, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
        styles[label.toLowerCase()] ?? 'bg-slate-50 text-slate-600 border border-slate-200'
      } ${className}`}
    >
      {label}
    </span>
  )
}

export function RiskBadge({ risk }: { risk: 'high' | 'medium' | 'low' }) {
  return <Badge label={risk} />
}
