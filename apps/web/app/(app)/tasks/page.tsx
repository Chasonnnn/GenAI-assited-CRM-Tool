"use client"

/**
 * Tasks Page - /tasks
 * 
 * Unified view showing tasks and appointments with list/calendar toggle.
 */

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PlusIcon, LoaderIcon, ListIcon, CalendarIcon, ShieldCheckIcon, ClockIcon } from "lucide-react"
import { UnifiedCalendar } from "@/components/appointments"
import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import { AddTaskDialog, type TaskFormData } from "@/components/tasks/AddTaskDialog"
import { ApprovalTaskActions } from "@/components/tasks/ApprovalTaskActions"
import { ApprovalStatusBadge } from "@/components/tasks/ApprovalStatusBadge"
import { useTasks, useCompleteTask, useUncompleteTask, useUpdateTask, useCreateTask, useDeleteTask } from "@/lib/hooks/use-tasks"
import { useAuth } from "@/lib/auth-context"
import { useAIContext } from "@/lib/context/ai-context"
import type { TaskListItem } from "@/lib/types/task"
import { parseDateInput, startOfLocalDay } from "@/lib/utils/date"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"
import { format, parseISO } from "date-fns"

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
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

// Check if task is due tomorrow
function isDueTomorrow(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const tomorrow = startOfLocalDay()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return due.getTime() === tomorrow.getTime()
}

// Check if task is due this week
function isDueThisWeek(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const today = startOfLocalDay()
    const endOfWeek = new Date(today)
    endOfWeek.setDate(today.getDate() + 7)
    return due > today && due <= endOfWeek && !isDueToday(dueDate) && !isDueTomorrow(dueDate)
}

type DueCategory = 'overdue' | 'today' | 'tomorrow' | 'this-week' | 'later' | 'no-date'

function getDueCategory(task: TaskListItem): DueCategory {
    if (!task.due_date) return 'no-date'
    if (isOverdue(task.due_date)) return 'overdue'
    if (isDueToday(task.due_date)) return 'today'
    if (isDueTomorrow(task.due_date)) return 'tomorrow'
    if (isDueThisWeek(task.due_date)) return 'this-week'
    return 'later'
}

const categoryLabels: Record<DueCategory, string> = {
    overdue: 'Overdue',
    today: 'Today',
    tomorrow: 'Tomorrow',
    'this-week': 'This Week',
    later: 'Later',
    'no-date': 'No Due Date',
}

const categoryColors: Record<DueCategory, { text: string; badge: string }> = {
    overdue: { text: 'text-destructive', badge: 'bg-destructive/10 text-destructive border-destructive/20' },
    today: { text: 'text-amber-500', badge: 'bg-amber-500/10 text-amber-500 border-amber-500/20' },
    tomorrow: { text: 'text-blue-500', badge: 'bg-blue-500/10 text-blue-500 border-blue-500/20' },
    'this-week': { text: 'text-muted-foreground', badge: 'bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20' },
    later: { text: 'text-muted-foreground', badge: 'bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20' },
    'no-date': { text: 'text-muted-foreground', badge: 'bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20' },
}

type FilterType = "all" | "my_tasks"
const VALID_FILTERS: FilterType[] = ["all", "my_tasks"]

export default function TasksPage() {
    const searchParams = useSearchParams()
    const router = useRouter()

    // Read initial values from URL params
    const urlFilter = searchParams.get("filter") as FilterType | null

    const [filter, setFilter] = useState<FilterType>(
        urlFilter && VALID_FILTERS.includes(urlFilter) ? urlFilter : "my_tasks"
    )
    const [showCompleted, setShowCompleted] = useState(false)
    const [view, setView] = useState<"list" | "calendar">(() => {
        if (typeof window !== "undefined") {
            return (localStorage.getItem("tasks-view") as "list" | "calendar") || "calendar"
        }
        return "calendar"
    })

    // Sync state changes back to URL
    const updateUrlParams = useCallback((filterValue: FilterType) => {
        const newParams = new URLSearchParams(searchParams.toString())
        if (filterValue !== "my_tasks") {
            newParams.set("filter", filterValue)
        } else {
            newParams.delete("filter")
        }
        const newUrl = newParams.toString() ? `?${newParams}` : ""
        router.replace(`/tasks${newUrl}`, { scroll: false })
    }, [searchParams, router])

    // Handle filter change
    const handleFilterChange = useCallback((newFilter: FilterType) => {
        setFilter(newFilter)
        updateUrlParams(newFilter)
    }, [updateUrlParams])

    const handleViewChange = (newView: "list" | "calendar") => {
        setView(newView)
        localStorage.setItem("tasks-view", newView)
    }

    // Create/edit modal state
    const [addTaskDialogOpen, setAddTaskDialogOpen] = useState(false)
    const [editingTask, setEditingTask] = useState<TaskListItem | null>(null)

    const handleTaskClick = (task: TaskListItem) => {
        setEditingTask(task)
    }

    const handleSaveTask = async (taskId: string, data: Partial<TaskListItem>) => {
        const payload: Record<string, unknown> = {}
        for (const [key, value] of Object.entries(data)) {
            payload[key] = value === null ? undefined : value
        }
        await updateTask.mutateAsync({ taskId, data: payload })
    }

    const handleDeleteTask = async (taskId: string) => {
        await deleteTask.mutateAsync(taskId)
        setEditingTask(null)
    }

    // Fetch incomplete tasks
    const { data: incompleteTasks, isLoading: loadingIncomplete, isError: incompleteError } = useTasks({
        my_tasks: filter === "my_tasks",
        is_completed: false,
        per_page: 100,
        exclude_approvals: true,
    })

    // Fetch completed tasks (only when shown)
    const { data: completedTasks, isLoading: loadingCompleted, isError: completedError } = useTasks({
        my_tasks: filter === "my_tasks",
        is_completed: true,
        per_page: 50,
        exclude_approvals: true,
    })

    // Fetch pending workflow approvals (always my_tasks)
    const { data: pendingApprovals, isLoading: loadingApprovals } = useTasks({
        my_tasks: true,
        task_type: "workflow_approval",
        status: ["pending", "in_progress"],
        exclude_approvals: false,
        per_page: 50,
    })

    // Get current user for ownership check
    const { user: currentUser } = useAuth()

    const completeTask = useCompleteTask()
    const uncompleteTask = useUncompleteTask()
    const updateTask = useUpdateTask()
    const createTask = useCreateTask()
    const deleteTask = useDeleteTask()

    // Set AI context when editing a task, clear when not
    const { setContext: setAIContext, clearContext: clearAIContext } = useAIContext()

    // Effect to update AI context when editing task changes
    useEffect(() => {
        if (editingTask) {
            setAIContext({
                entityType: "task" as const,
                entityId: editingTask.id,
                entityName: editingTask.title,
            })
        } else {
            clearAIContext()
        }
    }, [editingTask, setAIContext, clearAIContext])

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        if (isCompleted) {
            await uncompleteTask.mutateAsync(taskId)
        } else {
            await completeTask.mutateAsync(taskId)
        }
    }

    const handleAddTask = async (data: TaskFormData) => {
        const dueTime = data.due_time ? `${data.due_time}:00` : undefined

        if (data.recurrence === "none") {
            await createTask.mutateAsync({
                title: data.title,
                description: data.description,
                task_type: data.task_type,
                due_date: data.due_date,
                due_time: dueTime,
            })
            return
        }

        if (!data.due_date || !data.repeat_until) {
            return
        }

        const start = parseISO(data.due_date)
        const end = parseISO(data.repeat_until)
        const dates = buildRecurringDates(start, end, data.recurrence)

        if (dates.length >= MAX_TASK_OCCURRENCES && end > dates[dates.length - 1]) {
            return
        }

        for (const date of dates) {
            await createTask.mutateAsync({
                title: data.title,
                description: data.description,
                task_type: data.task_type,
                due_date: format(date, "yyyy-MM-dd"),
                due_time: dueTime,
            })
        }
    }

    // Group tasks by due category
    const groupedTasks = {
        overdue: [] as TaskListItem[],
        today: [] as TaskListItem[],
        tomorrow: [] as TaskListItem[],
        'this-week': [] as TaskListItem[],
        later: [] as TaskListItem[],
        'no-date': [] as TaskListItem[],
    }

    incompleteTasks?.items.forEach((task: TaskListItem) => {
        const category = getDueCategory(task)
        groupedTasks[category].push(task)
    })

    const renderTaskItem = (task: TaskListItem, showCategory = true) => {
        const category = getDueCategory(task)
        const colors = categoryColors[category]

        return (
            <div
                key={task.id}
                className={`flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50 ${task.is_completed ? 'opacity-60' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => handleTaskClick(task)}
                onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        handleTaskClick(task)
                    }
                }}
            >
                <Checkbox
                    className="mt-0.5"
                    checked={task.is_completed}
                    onCheckedChange={() => handleTaskToggle(task.id, task.is_completed)}
                    onClick={(event) => event.stopPropagation()}
                />
                <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                        <span className={`font-medium ${task.is_completed ? 'line-through' : ''}`}>{task.title}</span>
                        {showCategory && !task.is_completed && (
                            <Badge variant="secondary" className={colors.badge}>
                                {categoryLabels[category]}
                            </Badge>
                        )}
                    </div>
                    {task.case_id && (
                        <Link
                            href={`/cases/${task.case_id}`}
                            className="text-sm text-muted-foreground hover:underline"
                            onClick={(event) => event.stopPropagation()}
                        >
                            Case #{task.case_number}
                        </Link>
                    )}
                </div>
                {task.owner_name && (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger>
                                <Avatar className="size-8">
                                    <AvatarFallback>{getInitials(task.owner_name)}</AvatarFallback>
                                </Avatar>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>{task.owner_name}</p>
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                )}
            </div>
        )
    }

    const renderSection = (category: DueCategory, tasks: TaskListItem[]) => {
        if (tasks.length === 0) return null
        const colors = categoryColors[category]

        return (
            <div key={category} className="space-y-3">
                <div className="flex items-center gap-3">
                    <div className={`h-px flex-1 ${category === 'overdue' ? 'bg-destructive' : 'bg-border'}`} />
                    <h3 className={`text-sm font-medium ${colors.text}`}>
                        {categoryLabels[category]} ({tasks.length})
                    </h3>
                    <div className={`h-px flex-1 ${category === 'overdue' ? 'bg-destructive' : 'bg-border'}`} />
                </div>
                <div className="space-y-2">
                    {tasks.map(task => renderTaskItem(task, false))}
                </div>
            </div>
        )
    }

    const isLoading = loadingIncomplete
    const hasError = incompleteError || completedError

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Tasks</h1>
                    <Button onClick={() => setAddTaskDialogOpen(true)}>
                        <PlusIcon className="mr-2 size-4" />
                        Add Task
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6">
                <p className="text-sm text-muted-foreground">
                    Manage your tasks and appointments in one unified view.
                </p>

                {/* Filters Row */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex gap-2">
                        <Button
                            variant={filter === "my_tasks" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => handleFilterChange("my_tasks")}
                        >
                            My Tasks
                        </Button>
                        <Button
                            variant={filter === "all" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => handleFilterChange("all")}
                        >
                            All Tasks
                        </Button>
                    </div>

                    {/* View Toggle */}
                    <div className="flex gap-1 border rounded-lg p-1">
                        <Button
                            variant={view === "list" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => handleViewChange("list")}
                        >
                            <ListIcon className="size-4 mr-1" />
                            List
                        </Button>
                        <Button
                            variant={view === "calendar" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => handleViewChange("calendar")}
                        >
                            <CalendarIcon className="size-4 mr-1" />
                            Calendar
                        </Button>
                    </div>
                </div>

                {/* Loading State */}
                {isLoading && (
                    <Card className="flex items-center justify-center p-12">
                        <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading tasks...</span>
                    </Card>
                )}

                {/* Error State */}
                {!isLoading && hasError && (
                    <Card className="flex items-center justify-center p-12 border-destructive/40 bg-destructive/5">
                        <span className="text-destructive">Unable to load tasks. Please try again.</span>
                    </Card>
                )}

                {/* Calendar View */}
                {!isLoading && !hasError && view === "calendar" && (
                    <UnifiedCalendar
                        taskFilter={{ my_tasks: filter === "my_tasks" }}
                        onTaskClick={handleTaskClick}
                    />
                )}

                {/* Pending Approvals Section */}
                {!isLoading && !hasError && (
                    <Card className="overflow-hidden border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent">
                        <div className="border-b border-amber-500/20 bg-amber-500/5 px-4 py-3 sm:px-6 sm:py-4">
                            <div className="flex items-center gap-3">
                                <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 sm:size-9">
                                    <ShieldCheckIcon className="size-4 sm:size-5" />
                                </div>
                                <div>
                                    <h2 className="text-sm font-semibold text-amber-700 dark:text-amber-500 sm:text-base">
                                        Pending Approvals
                                    </h2>
                                    <p className="text-xs text-amber-600/80 dark:text-amber-500/70 sm:text-sm">
                                        {pendingApprovals?.items?.length || 0} workflow action{pendingApprovals?.items?.length !== 1 ? 's' : ''} awaiting review
                                    </p>
                                </div>
                            </div>
                        </div>
                        <div className="divide-y divide-border">
                            {loadingApprovals ? (
                                <div className="flex items-center justify-center py-8">
                                    <LoaderIcon className="size-5 animate-spin text-muted-foreground" />
                                </div>
                            ) : pendingApprovals?.items?.length ? (
                                pendingApprovals.items.map((approval: TaskListItem) => {
                                    const isOwner = currentUser?.user_id === approval.owner_id
                                    const dueAt = approval.due_at ? new Date(approval.due_at) : null
                                    const now = new Date()
                                    const hoursRemaining = dueAt ? Math.max(0, Math.round((dueAt.getTime() - now.getTime()) / (1000 * 60 * 60))) : null
                                    const isUrgent = hoursRemaining !== null && hoursRemaining < 8

                                    return (
                                        <div
                                            key={approval.id}
                                            className="group flex flex-col gap-3 p-3 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4"
                                        >
                                            <div className="flex-1 space-y-2">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="font-medium">{approval.title}</span>
                                                    <ApprovalStatusBadge status={approval.status || 'pending'} />
                                                </div>
                                                {approval.workflow_action_preview && (
                                                    <p className="text-sm text-muted-foreground">
                                                        {approval.workflow_action_preview}
                                                    </p>
                                                )}
                                                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                                    {approval.case_id && (
                                                        <Link
                                                            href={`/cases/${approval.case_id}`}
                                                            className="hover:text-foreground hover:underline"
                                                        >
                                                            Case #{approval.case_number}
                                                        </Link>
                                                    )}
                                                    {hoursRemaining !== null && (
                                                        <span className={`flex items-center gap-1 ${isUrgent ? 'text-amber-600 font-medium' : ''}`}>
                                                            <ClockIcon className="size-3" />
                                                            {hoursRemaining > 24
                                                                ? `${Math.floor(hoursRemaining / 24)}d ${hoursRemaining % 24}h remaining`
                                                                : hoursRemaining > 0
                                                                    ? `${hoursRemaining}h remaining`
                                                                    : 'Due now'
                                                            }
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex-shrink-0">
                                                <ApprovalTaskActions
                                                    taskId={approval.id}
                                                    isOwner={isOwner}
                                                />
                                            </div>
                                        </div>
                                    )
                                })
                            ) : (
                                <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                                    No pending approvals right now.
                                </div>
                            )}
                        </div>
                    </Card>
                )}

                {/* List View */}
                {!isLoading && !hasError && view === "list" && (
                    <Card className="p-6">
                        <div className="space-y-6">
                            {/* Task sections by due date */}
                            {renderSection('overdue', groupedTasks.overdue)}
                            {renderSection('today', groupedTasks.today)}
                            {renderSection('tomorrow', groupedTasks.tomorrow)}
                            {renderSection('this-week', groupedTasks['this-week'])}
                            {renderSection('later', groupedTasks.later)}
                            {renderSection('no-date', groupedTasks['no-date'])}

                            {/* Empty state */}
                            {incompleteTasks?.items.length === 0 && (
                                <p className="text-center text-muted-foreground py-8">
                                    No pending tasks. Nice work!
                                </p>
                            )}

                            {/* Completed Tasks Section */}
                            <div className="border-t border-border pt-4">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setShowCompleted(!showCompleted)}
                                    className="w-full justify-center"
                                >
                                    {showCompleted ? "Hide" : "Show"} completed tasks ({completedTasks?.total || 0})
                                </Button>

                                {showCompleted && completedTasks && (
                                    <div className="mt-4 space-y-2">
                                        {loadingCompleted ? (
                                            <div className="flex items-center justify-center py-4">
                                                <LoaderIcon className="size-4 animate-spin text-muted-foreground" />
                                            </div>
                                        ) : completedError ? (
                                            <p className="text-center text-destructive py-4">Unable to load completed tasks</p>
                                        ) : completedTasks.items.length === 0 ? (
                                            <p className="text-center text-muted-foreground py-4">No completed tasks</p>
                                        ) : (
                                            completedTasks.items.map((task: TaskListItem) => renderTaskItem(task))
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    </Card>
                )}

                {/* Edit Modal */}
                <TaskEditModal
                    task={editingTask ? {
                        id: editingTask.id,
                        title: editingTask.title,
                        description: editingTask.description ?? null,
                        task_type: editingTask.task_type,
                        due_date: editingTask.due_date,
                        due_time: editingTask.due_time ?? null,
                        is_completed: editingTask.is_completed,
                        case_id: editingTask.case_id,
                    } : null}
                    open={!!editingTask}
                    onClose={() => setEditingTask(null)}
                    onSave={(taskId, data) => handleSaveTask(taskId, data as Partial<TaskListItem>)}
                    onDelete={handleDeleteTask}
                    isDeleting={deleteTask.isPending}
                />
                <AddTaskDialog
                    open={addTaskDialogOpen}
                    onOpenChange={setAddTaskDialogOpen}
                    onSubmit={handleAddTask}
                    isPending={createTask.isPending}
                />
            </div>
        </div>
    )
}
