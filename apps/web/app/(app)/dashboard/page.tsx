"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  CheckSquareIcon,
  UsersIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  ArrowUpIcon,
  LoaderIcon,
  AlertCircleIcon,
} from "lucide-react"
import { useMemo } from "react"
import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis, Cell } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { useCaseStats } from "@/lib/hooks/use-cases"
import { useTasks, useCompleteTask, useUncompleteTask } from "@/lib/hooks/use-tasks"
import { useCasesTrend, useCasesByStatus } from "@/lib/hooks/use-analytics"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useAuth } from "@/lib/auth-context"
import { useDashboardSocket } from "@/lib/hooks/use-dashboard-socket"
import type { TaskListItem } from "@/lib/types/task"
import { parseDateInput, startOfLocalDay } from "@/lib/utils/date"

// Format relative time
function formatRelativeTime(dateString: string): string {
  const date = parseDateInput(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  return `${diffDays}d ago`
}

// Check if task is overdue
function isOverdue(dueDate: string | null): boolean {
  if (!dueDate) return false
  return parseDateInput(dueDate) < startOfLocalDay()
}

// Check if task is due today
function isDueToday(dueDate: string | null): boolean {
  if (!dueDate) return false
  const due = parseDateInput(dueDate)
  const today = startOfLocalDay()
  return due.getTime() === today.getTime()
}

// Get due badge variant
function getDueBadge(dueDate: string | null, isCompleted: boolean): { label: string; variant: string } | null {
  if (isCompleted || !dueDate) return null
  if (isOverdue(dueDate)) return { label: 'Overdue', variant: 'destructive' }
  if (isDueToday(dueDate)) return { label: 'Today', variant: 'bg-amber-500 hover:bg-amber-500/80' }

  const due = parseDateInput(dueDate)
  const tomorrow = startOfLocalDay()
  tomorrow.setDate(tomorrow.getDate() + 1)
  if (due.getTime() === tomorrow.getTime()) return { label: 'Tomorrow', variant: 'secondary' }

  const nextWeek = startOfLocalDay()
  nextWeek.setDate(nextWeek.getDate() + 7)
  if (due <= nextWeek) return { label: 'This Week', variant: 'secondary' }

  return { label: 'Upcoming', variant: 'secondary' }
}

// Get user's first name
function getFirstName(displayName: string | undefined): string {
  if (!displayName) return 'there'
  return displayName.split(' ')[0]
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { data: stats, isLoading: statsLoading, isError: statsError } = useCaseStats()
  const { data: tasksData, isLoading: tasksLoading, isError: tasksError } = useTasks({ my_tasks: true, is_completed: false, per_page: 5 })
  const { data: trendData, isLoading: trendLoading, isError: trendError } = useCasesTrend({ period: 'day' })
  const { data: statusData, isLoading: statusLoading, isError: statusError } = useCasesByStatus()
  const { data: defaultPipeline } = useDefaultPipeline()
  const completeTask = useCompleteTask()
  const uncompleteTask = useUncompleteTask()

  // WebSocket for real-time updates (falls back to polling if disconnected)
  useDashboardSocket()

  const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
    if (isCompleted) {
      await uncompleteTask.mutateAsync(taskId)
    } else {
      await completeTask.mutateAsync(taskId)
    }
  }

  // Count overdue tasks
  const overdueCount = tasksError
    ? 0
    : tasksData?.items.filter((t: TaskListItem) => !t.is_completed && isOverdue(t.due_date)).length || 0
  const pendingTasksCount = tasksError ? 0 : tasksData?.items.length || 0

  // Current date for header
  const currentDate = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })

  // Transform trend data for chart
  const chartTrendData = trendData?.map((item: { date: string; count: number }) => ({
    date: parseDateInput(item.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    cases: item.count,
  })) || []

  const stageByLabel = useMemo(() => {
    const stages = defaultPipeline?.stages || []
    return new Map(stages.map(stage => [stage.label, stage]))
  }, [defaultPipeline])

  // Transform status data for bar chart (StatusCount[] from API) with stage colors
  const chartStatusData = Array.isArray(statusData) ? statusData.map((item) => {
    const stage = stageByLabel.get(item.status)
    return {
      status: stage?.label || item.status,
      count: item.count,
      fill: stage?.color || '#6b7280',
    }
  }) : []

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      {/* Welcome Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Welcome back, {getFirstName(user?.display_name)}</h1>
          <p className="text-sm text-muted-foreground">{currentDate}</p>
        </div>
      </div>

      {/* Stats Cards - 4 columns */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {/* Active Cases */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Active Cases</CardTitle>
              {stats?.week_change_pct !== null && stats?.week_change_pct !== undefined && (
                <div className={`flex items-center gap-1 text-xs font-medium ${(stats.week_change_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(stats.week_change_pct || 0) >= 0 ? <TrendingUpIcon className="h-3 w-3" /> : <TrendingDownIcon className="h-3 w-3" />}
                  {(stats.week_change_pct || 0) >= 0 ? '+' : ''}{stats.week_change_pct}%
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {statsLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : statsError ? (
              <div className="flex items-center text-xs text-destructive">
                <AlertCircleIcon className="mr-1 h-4 w-4" />
                Unable to load
              </div>
            ) : (
              <>
                <div className="text-3xl font-bold">{stats?.total || 0}</div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-sm font-medium">
                    {stats?.this_week || 0} new this week
                  </div>
                  <p className="text-xs text-muted-foreground">
                    vs {stats?.last_week || 0} last week
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Pending Tasks */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Pending Tasks</CardTitle>
              {overdueCount > 0 ? (
                <div className="flex items-center gap-1 text-xs font-medium text-red-600">
                  <TrendingDownIcon className="h-3 w-3" />
                  {overdueCount} overdue
                </div>
              ) : (
                <div className="flex items-center gap-1 text-xs font-medium text-green-600">
                  <TrendingUpIcon className="h-3 w-3" />
                  On track
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {statsLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : statsError ? (
              <div className="flex items-center text-xs text-destructive">
                <AlertCircleIcon className="mr-1 h-4 w-4" />
                Unable to load
              </div>
            ) : (
              <>
                <div className="text-3xl font-bold">{stats?.pending_tasks || 0}</div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-sm font-medium">
                    {overdueCount > 0 ? 'Needs attention' : 'All tasks on schedule'}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {overdueCount > 0 ? `${overdueCount} overdue tasks` : 'No overdue tasks'}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* New Leads (30 days) */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">New Leads (30d)</CardTitle>
              {stats?.month_change_pct !== null && stats?.month_change_pct !== undefined && (
                <div className={`flex items-center gap-1 text-xs font-medium ${(stats.month_change_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(stats.month_change_pct || 0) >= 0 ? <TrendingUpIcon className="h-3 w-3" /> : <TrendingDownIcon className="h-3 w-3" />}
                  {(stats.month_change_pct || 0) >= 0 ? '+' : ''}{stats.month_change_pct}%
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {statsLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : statsError ? (
              <div className="flex items-center text-xs text-destructive">
                <AlertCircleIcon className="mr-1 h-4 w-4" />
                Unable to load
              </div>
            ) : (
              <>
                <div className="text-3xl font-bold">{stats?.this_month || 0}</div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-sm font-medium">
                    Monthly intake volume
                    <UsersIcon className="h-3 w-3" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    vs {stats?.last_month || 0} last month
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* My Tasks */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">My Tasks</CardTitle>
              <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                <CheckSquareIcon className="h-3 w-3" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {tasksLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : tasksError ? (
              <div className="flex items-center text-xs text-destructive">
                <AlertCircleIcon className="mr-1 h-4 w-4" />
                Unable to load
              </div>
            ) : (
              <>
                <div className="text-3xl font-bold">{pendingTasksCount}</div>
                <div className="space-y-1">
                  <div className="flex items-center gap-1 text-sm font-medium">
                    {pendingTasksCount === 0 ? 'All caught up!' : 'Tasks assigned to you'}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    <Link href="/tasks" className="hover:underline">View all tasks →</Link>
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Section - Two horizontal */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Cases Trend Chart */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Cases Trend</CardTitle>
            <CardDescription className="text-sm">New cases over the last 30 days</CardDescription>
          </CardHeader>
          <CardContent className="pb-4">
            {trendLoading ? (
              <div className="flex items-center justify-center h-[280px]">
                <LoaderIcon className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : trendError ? (
              <div className="flex items-center justify-center h-[280px] text-destructive">
                <AlertCircleIcon className="mr-2 h-4 w-4" />
                Unable to load data
              </div>
            ) : chartTrendData.length === 0 ? (
              <div className="flex items-center justify-center h-[280px] text-muted-foreground">
                No data available
              </div>
            ) : (
              <ChartContainer
                config={{
                  cases: {
                    label: "Cases",
                    color: "var(--chart-1)",
                  },
                }}
                className="h-[280px] w-full"
              >
                <AreaChart
                  accessibilityLayer
                  data={chartTrendData}
                  margin={{ left: 12, right: 12 }}
                >
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                  />
                  <ChartTooltip
                    cursor={false}
                    content={<ChartTooltipContent indicator="line" />}
                  />
                  <Area
                    dataKey="cases"
                    type="natural"
                    fill="var(--color-cases)"
                    fillOpacity={0.4}
                    stroke="var(--color-cases)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        {/* Cases by Status Chart */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Cases by Status</CardTitle>
            <CardDescription className="text-sm">Current pipeline distribution</CardDescription>
          </CardHeader>
          <CardContent className="pb-4">
            {statusLoading ? (
              <div className="flex items-center justify-center h-[280px]">
                <LoaderIcon className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : statusError ? (
              <div className="flex items-center justify-center h-[280px] text-destructive">
                <AlertCircleIcon className="mr-2 h-4 w-4" />
                Unable to load data
              </div>
            ) : chartStatusData.length === 0 ? (
              <div className="flex items-center justify-center h-[280px] text-muted-foreground">
                No data available
              </div>
            ) : (
              <ChartContainer
                config={{
                  count: {
                    label: "Cases",
                    color: "var(--chart-2)",
                  },
                }}
                className="h-[280px] w-full"
              >
                <BarChart
                  accessibilityLayer
                  data={chartStatusData}
                  layout="vertical"
                  margin={{ left: 80, right: 12 }}
                >
                  <CartesianGrid horizontal={false} />
                  <XAxis type="number" tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="status"
                    tickLine={false}
                    axisLine={false}
                    width={75}
                  />
                  <ChartTooltip
                    cursor={false}
                    content={<ChartTooltipContent indicator="dashed" />}
                  />
                  <Bar dataKey="count" radius={4}>
                    {chartStatusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tasks & Activity Section */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* My Tasks Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>My Tasks</CardTitle>
            <Link href="/tasks">
              <Button variant="link" className="h-auto p-0 text-sm">
                View All
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {tasksLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : tasksError ? (
              <div className="flex items-center justify-center py-8 text-destructive">
                <AlertCircleIcon className="mr-2 h-4 w-4" />
                Unable to load tasks
              </div>
            ) : tasksData?.items.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No pending tasks</p>
            ) : (
              tasksData?.items.map((task: TaskListItem) => {
                const dueBadge = getDueBadge(task.due_date, task.is_completed)
                return (
                  <div key={task.id} className="flex items-start gap-3">
                    <Checkbox
                      id={`task-${task.id}`}
                      className="mt-1"
                      checked={task.is_completed}
                      onCheckedChange={() => handleTaskToggle(task.id, task.is_completed)}
                    />
                    <div className="flex-1 space-y-1">
                      <label
                        htmlFor={`task-${task.id}`}
                        className={`text-sm font-medium leading-none ${task.is_completed ? 'line-through text-muted-foreground' : ''}`}
                      >
                        {task.title}
                      </label>
                      <div className="flex items-center gap-2">
                        {dueBadge && (
                          <Badge
                            variant={dueBadge.variant === 'destructive' ? 'destructive' : 'secondary'}
                            className={`text-xs ${dueBadge.variant.startsWith('bg-') ? dueBadge.variant : ''}`}
                          >
                            {dueBadge.label}
                          </Badge>
                        )}
                        {task.case_number && (
                          <Link
                            href={`/cases/${task.case_id}`}
                            className="text-xs text-muted-foreground hover:underline"
                          >
                            #{task.case_number}
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>

        {/* Cases by Status Breakdown */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Status Breakdown</CardTitle>
            <Link href="/cases">
              <Button variant="link" className="h-auto p-0 text-sm">
                View All
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="space-y-4">
            {statsLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : statsError ? (
              <div className="flex items-center justify-center py-8 text-destructive">
                <AlertCircleIcon className="mr-2 h-4 w-4" />
                Unable to load status data
              </div>
            ) : stats?.by_status && Object.keys(stats.by_status).length > 0 ? (
              Object.entries(stats.by_status).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className="text-sm capitalize">{status.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-medium">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">No cases yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
