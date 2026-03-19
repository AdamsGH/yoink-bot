import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { apiClient } from '@/lib/api-client'
import { cn } from '@/lib/utils'
import type { StatsOverview } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/components/ui/toast'

const CHART_COLORS = [
  'hsl(221.2 83.2% 53.3%)',
  'hsl(262.1 83.3% 57.8%)',
  'hsl(346.8 77.2% 49.8%)',
  'hsl(142.1 76.2% 36.3%)',
  'hsl(24.6 95% 53.1%)',
]

const PERIOD_OPTIONS = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
] as const

type Period = (typeof PERIOD_OPTIONS)[number]['value']

function PeriodToggle({ value, onChange }: { value: Period; onChange: (v: Period) => void }) {
  return (
    <div className="flex rounded-md border">
      {PERIOD_OPTIONS.map((opt) => (
        <Button
          key={opt.value}
          variant="ghost"
          size="sm"
          onClick={() => onChange(opt.value)}
          className={cn(
            'h-8 rounded-none px-3 text-xs first:rounded-l-md last:rounded-r-md',
            value === opt.value && 'bg-muted font-semibold',
          )}
        >
          {opt.label}
        </Button>
      ))}
    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
  variant = 'default',
}: {
  label: string
  value: string | number
  sub?: string
  variant?: 'default' | 'danger' | 'success'
}) {
  const valueClass =
    variant === 'danger'
      ? 'text-destructive'
      : variant === 'success'
        ? 'text-green-600 dark:text-green-400'
        : 'text-primary'

  return (
    <Card className="select-none">
      <CardContent className="pt-5">
        <div className={cn('text-3xl font-bold tabular-nums', valueClass)}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        <div className="mt-1 text-sm text-muted-foreground">{label}</div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  )
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="pt-5 space-y-2">
        <Skeleton className="h-9 w-20" />
        <Skeleton className="h-4 w-28" />
      </CardContent>
    </Card>
  )
}

export default function AdminStatsPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState<Period>(30)

  useEffect(() => {
    setLoading(true)
    apiClient
      .get<StatsOverview>('/stats/overview', { params: { days: period } })
      .then((res) => setStats(res.data))
      .catch(() => toast.error('Failed to load stats'))
      .finally(() => setLoading(false))
  }, [period])

  const cacheRate =
    stats && stats.total_downloads > 0
      ? Math.round((stats.cache_hits_today / Math.max(stats.downloads_today, 1)) * 100)
      : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Statistics</h1>
        <PeriodToggle value={period} onChange={setPeriod} />
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard label="Total downloads" value={stats.total_downloads} />
            <StatCard label="Today" value={stats.downloads_today} variant="success" />
            <StatCard
              label="Cache hits today"
              value={stats.cache_hits_today}
              sub={`${cacheRate}% of today`}
            />
            <StatCard
              label="Errors today"
              value={stats.errors_today}
              variant={stats.errors_today > 0 ? 'danger' : 'default'}
            />
          </>
        )}
      </div>

      {/* Downloads chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Downloads  - last {period} days</CardTitle>
        </CardHeader>
        <CardContent>
          {loading || !stats ? (
            <Skeleton className="h-48 w-full" />
          ) : stats.downloads_by_day.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              No data
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={stats.downloads_by_day}
                margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v: string) => v.slice(5)}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip
                  labelFormatter={(v) => `Date: ${v}`}
                  formatter={(v) => [v, 'Downloads']}
                />
                <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Bottom 2-col */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Top domains</CardTitle>
          </CardHeader>
          <CardContent>
            {loading || !stats ? (
              <Skeleton className="h-44 w-full" />
            ) : stats.top_domains.length === 0 ? (
              <div className="text-sm text-muted-foreground">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={stats.top_domains.slice(0, 8)}
                  layout="vertical"
                  margin={{ top: 0, right: 12, left: 4, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-border" />
                  <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                  <YAxis type="category" dataKey="domain" width={88} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v) => [v, 'Downloads']} />
                  <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                    {stats.top_domains.slice(0, 8).map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Domain share</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            {loading || !stats ? (
              <Skeleton className="h-44 w-full" />
            ) : stats.top_domains.length === 0 ? (
              <div className="text-sm text-muted-foreground">No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={stats.top_domains.slice(0, 6)}
                    dataKey="count"
                    nameKey="domain"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    label={({ name, percent }) =>
                      `${name ?? ''} ${percent != null ? (percent * 100).toFixed(0) : 0}%`
                    }
                    labelLine={false}
                  >
                    {stats.top_domains.slice(0, 6).map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [v, 'Downloads']} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
