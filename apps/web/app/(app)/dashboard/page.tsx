"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  FolderIcon,
  CheckSquareIcon,
  ClockIcon,
  PlusIcon,
  LoaderIcon,
} from "lucide-react"
import { useCaseStats } from "@/lib/hooks/use-cases"
import { useTasks, useCompleteTask, useUncompleteTask } from "@/lib/hooks/use-tasks"
import type { TaskListItem } from "@/lib/types/task"

// Format relative time
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
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
  return new Date(dueDate) < new Date()
}

// Check if task is due today
function isDueToday(dueDate: string | null): boolean {
  if (!dueDate) return false
  const due = new Date(dueDate)
  const today = new Date()
  return due.toDateString() === today.toDateString()
}

// Get due badge variant
function getDueBadge(dueDate: string | null, isCompleted: boolean): { label: string; variant: string } | null {
  if (isCompleted || !dueDate) return null
  if (isOverdue(dueDate)) return { label: 'Overdue', variant: 'destructive' }
  if (isDueToday(dueDate)) return { label: 'Today', variant: 'bg-amber-500 hover:bg-amber-500/80' }

  const due = new Date(dueDate)
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  if (due.toDateString() === tomorrow.toDateString()) return { label: 'Tomorrow', variant: 'secondary' }

  const nextWeek = new Date()
  nextWeek.setDate(nextWeek.getDate() + 7)
  if (due <= nextWeek) return { label: 'This Week', variant: 'secondary' }

  return { label: 'Upcoming', variant: 'secondary' }
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useCaseStats()
  const { data: tasksData, isLoading: tasksLoading } = useTasks({ my_tasks: true, is_completed: false, per_page: 5 })
  const completeTask = useCompleteTask()
  const uncompleteTask = useUncompleteTask()

  const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
    if (isCompleted) {
      await uncompleteTask.mutateAsync(taskId)
    } else {
      await completeTask.mutateAsync(taskId)
    }
  }

  // Count overdue tasks
  const overdueCount = tasksData?.items.filter((t: TaskListItem) => !t.is_completed && isOverdue(t.due_date)).length || 0

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Cases</CardTitle>
            <FolderIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.total || 0}</div>
                <p className="text-xs text-muted-foreground">{stats?.this_week || 0} new this week</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Tasks</CardTitle>
            <CheckSquareIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.pending_tasks || 0}</div>
                {overdueCount > 0 ? (
                  <p className="text-xs text-destructive">{overdueCount} overdue</p>
                ) : (
                  <p className="text-xs text-muted-foreground">All on track</p>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cases This Month</CardTitle>
            <ClockIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <LoaderIcon className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.this_month || 0}</div>
                <p className="text-xs text-muted-foreground">Last 30 days</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tasks & Activity */}
      <div className="grid gap-4 md:grid-cols-[1.6fr_1fr]">
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
            ) : tasksData?.items.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No pending tasks</p>
            ) : (
              tasksData?.items.map((task) => {
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

            <div className="flex items-center gap-2 pt-2">
              <Input placeholder="Add a task..." className="flex-1" disabled />
              <Button size="icon" variant="ghost" disabled>
                <PlusIcon className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Status Breakdown Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Cases by Status</CardTitle>
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