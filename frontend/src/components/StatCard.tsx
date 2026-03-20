interface StatCardProps {
  label: string
  value: string | number
  icon: React.ComponentType<{ className?: string }>
  iconBg: string
  iconColor: string
  trend?: string
  trendPositive?: boolean
}

export function StatCard({
  label, value, icon: Icon, iconBg, iconColor, trend, trendPositive = true,
}: StatCardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <div className={`${iconBg} w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
        {trend && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            trendPositive
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-red-50 text-red-700'
          }`}>
            {trend}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-slate-900 mt-3 tabular-nums">{value}</p>
      <p className="text-xs text-slate-500 mt-0.5 font-medium uppercase tracking-wide">{label}</p>
    </div>
  )
}
