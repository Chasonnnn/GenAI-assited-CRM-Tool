"use client"

/**
 * Tasks Page - /tasks
 * 
 * Unified view showing tasks and appointments with list/calendar toggle.
 */

import { useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PlusIcon, Loader2Icon, ListIcon, CalendarIcon } from "lucide-react"
import { TasksCalendarView } from "@/components/tasks/TasksCalendarView"
import { TasksListView } from "@/components/tasks/TasksListView"
import { TasksApprovalsSection } from "@/components/tasks/TasksApprovalsSection"
import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import { AddTaskDialog, type TaskFormData } from "@/components/tasks/AddTaskDialog"
import { useTasks, useCompleteTask, useUncompleteTask, useUpdateTask, useCreateTask, useDeleteTask, useBulkCompleteTasks } from "@/lib/hooks/use-tasks"
import { useStatusChangeRequests } from "@/lib/hooks/use-status-change-requests"
import { usePendingImportApprovals } from "@/lib/hooks/use-import"
import { useAuth } from "@/lib/auth-context"
import { useAIContext } from "@/lib/context/ai-context"
import type { TaskListItem } from "@/lib/types/task"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"
import { format, parseISO } from "date-fns"
import { toast } from "sonner"

type FilterType = "all" | "my_tasks"
const isFilterType = (value: string | null): value is FilterType =>
    value === "all" || value === "my_tasks"

type ViewType = "list" | "calendar"
const isViewType = (value: string | null): value is ViewType =>
    value === "list" || value === "calendar"

type FocusTarget =
    | "approvals"
    | "tasks"
    | "overdue"
    | "today"
    | "tomorrow"
    | "this-week"
    | "later"
    | "no-date"
const isFocusTarget = (value: string | null): value is FocusTarget =>
    value === "approvals" ||
    value === "tasks" ||
    value === "overdue" ||
    value === "today" ||
    value === "tomorrow" ||
    value === "this-week" ||
    value === "later" ||
    value === "no-date"

type TaskEditPayload = {
    id: string
    title: string
    description: string | null
    task_type: string
    due_date: string | null
    due_time: string | null
    is_completed: boolean
    surrogate_id: string | null
}

export default function TasksPage() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const { user: currentUser } = useAuth()
    const canApproveImports = ["admin", "developer"].includes(currentUser?.role || "")
    const currentUserId = currentUser?.user_id ?? null

    // Read initial values from URL params
    const urlFilter = searchParams.get("filter")
    const urlFocus = searchParams.get("focus")
    const urlOwnerId = searchParams.get("owner_id")
    const canViewOtherOwners = ["admin", "developer"].includes(currentUser?.role || "")
    const ownerOverride = canViewOtherOwners && urlOwnerId ? urlOwnerId : null

    const [filter, setFilter] = useState<FilterType>(
        isFilterType(urlFilter) ? urlFilter : "my_tasks"
    )
    const [pendingFocus, setPendingFocus] = useState<FocusTarget | null>(
        isFocusTarget(urlFocus) ? urlFocus : null
    )
    const [showCompleted, setShowCompleted] = useState(false)
    const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set())
    const [view, setView] = useState<ViewType>(() => {
        if (typeof window !== "undefined") {
            const stored = localStorage.getItem("tasks-view")
            return isViewType(stored) ? stored : "calendar"
        }
        return "calendar"
    })

    useEffect(() => {
        setPendingFocus(isFocusTarget(urlFocus) ? urlFocus : null)
    }, [urlFocus])

    // Sync state changes back to URL
    const updateUrlParams = useCallback((filterValue: FilterType) => {
        const newParams = new URLSearchParams(searchParams.toString())
        if (filterValue !== "my_tasks") {
            newParams.set("filter", filterValue)
        } else {
            newParams.delete("filter")
        }
        const nextQuery = newParams.toString()
        const currentQuery = searchParams.toString()
        if (nextQuery === currentQuery) return
        const newUrl = nextQuery ? `/tasks?${nextQuery}` : "/tasks"
        const currentUrl = currentQuery ? `/tasks?${currentQuery}` : "/tasks"
        if (newUrl === currentUrl) return
        router.replace(newUrl, { scroll: false })
    }, [searchParams, router])

    // Handle filter change
    const handleFilterChange = useCallback((newFilter: FilterType) => {
        setFilter(newFilter)
        updateUrlParams(newFilter)
    }, [updateUrlParams])

    const handleViewChange = (newView: ViewType) => {
        setView(newView)
        localStorage.setItem("tasks-view", newView)
    }

    // Create/edit modal state
    const [addTaskDialogOpen, setAddTaskDialogOpen] = useState(false)
    const [editingTask, setEditingTask] = useState<TaskListItem | null>(null)

    const handleTaskClick = (task: TaskListItem) => {
        setEditingTask(task)
    }

    const handleSaveTask = async (taskId: string, data: Partial<TaskEditPayload>) => {
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

    const taskOwnerId = ownerOverride ?? undefined
    const useMyTasks = !taskOwnerId && filter === "my_tasks"
    const ownerParams = taskOwnerId ? { owner_id: taskOwnerId } : {}

    // Fetch incomplete tasks
    const {
        data: incompleteTasks,
        isLoading: loadingIncomplete,
        isError: incompleteError,
        refetch: refetchIncomplete,
    } = useTasks({
        my_tasks: useMyTasks,
        ...ownerParams,
        is_completed: false,
        per_page: 100,
        exclude_approvals: true,
    })

    // Fetch completed tasks (only when shown)
    const {
        data: completedTasks,
        isLoading: loadingCompleted,
        isError: completedError,
        refetch: refetchCompleted,
    } = useTasks({
        my_tasks: useMyTasks,
        ...ownerParams,
        is_completed: true,
        per_page: 50,
        exclude_approvals: true,
    })

    // Fetch pending workflow approvals (always my_tasks)
    const { data: pendingApprovals, isLoading: loadingApprovals } = useTasks({
        my_tasks: !taskOwnerId,
        ...ownerParams,
        task_type: "workflow_approval",
        status: ["pending", "in_progress"],
        exclude_approvals: false,
        per_page: 50,
    })

    const {
        data: pendingImportApprovals,
        isLoading: loadingImportApprovals,
        refetch: refetchImportApprovals,
    } = usePendingImportApprovals(canApproveImports)

    const canViewStatusRequests = ["admin", "developer"].includes(currentUser?.role || "")

    // Fetch pending status change requests (admin/developer only)
    const { data: pendingStatusRequests, isLoading: loadingStatusRequests, refetch: refetchStatusRequests } = useStatusChangeRequests(
        {
            page: 1,
            per_page: 50,
        },
        canViewStatusRequests
    )

    const completeTask = useCompleteTask()
    const uncompleteTask = useUncompleteTask()
    const bulkCompleteTasks = useBulkCompleteTasks()
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
        setSelectedTaskIds((prev) => {
            if (!prev.has(taskId)) return prev
            const next = new Set(prev)
            next.delete(taskId)
            return next
        })
        if (isCompleted) {
            await uncompleteTask.mutateAsync(taskId)
        } else {
            await completeTask.mutateAsync(taskId)
        }
    }

    const handleSelectTask = useCallback((taskId: string, selected: boolean) => {
        setSelectedTaskIds((prev) => {
            const next = new Set(prev)
            if (selected) {
                next.add(taskId)
            } else {
                next.delete(taskId)
            }
            return next
        })
    }, [])

    const handleSelectAllTasks = useCallback((selected: boolean) => {
        if (!selected) {
            setSelectedTaskIds(new Set())
            return
        }
        const visibleTaskIds = (incompleteTasks?.items ?? []).map((task) => task.id)
        setSelectedTaskIds(new Set(visibleTaskIds))
    }, [incompleteTasks?.items])

    const handleBulkCompleteSelected = useCallback(async () => {
        const taskIds = Array.from(selectedTaskIds)
        if (taskIds.length === 0) return
        const result = await bulkCompleteTasks.mutateAsync(taskIds)
        setSelectedTaskIds(new Set())
        if (result.failed.length > 0) {
            toast.warning(
                `Completed ${result.completed} tasks, ${result.failed.length} failed.`
            )
            return
        }
        toast.success(`Completed ${result.completed} tasks.`)
    }, [bulkCompleteTasks, selectedTaskIds])

    const handleAddTask = async (data: TaskFormData) => {
        const dueTime = data.due_time ? `${data.due_time}:00` : undefined
        const buildPayload = (dueDate?: string) => ({
            title: data.title,
            task_type: data.task_type,
            ...(data.description ? { description: data.description } : {}),
            ...(dueDate ? { due_date: dueDate } : {}),
            ...(dueTime ? { due_time: dueTime } : {}),
        })

        if (data.recurrence === "none") {
            await createTask.mutateAsync(buildPayload(data.due_date))
            return
        }

        if (!data.due_date || !data.repeat_until) {
            return
        }

        const start = parseISO(data.due_date)
        const end = parseISO(data.repeat_until)
        const dates = buildRecurringDates(start, end, data.recurrence)

        const lastDate = dates[dates.length - 1]
        if (dates.length >= MAX_TASK_OCCURRENCES && lastDate && end > lastDate) {
            return
        }

        for (const date of dates) {
            await createTask.mutateAsync(buildPayload(format(date, "yyyy-MM-dd")))
        }
    }

    const isLoading = loadingIncomplete
    const hasError = incompleteError || completedError
    const handleRetry = () => {
        refetchIncomplete()
        refetchCompleted()
    }

    useEffect(() => {
        if (!pendingFocus || pendingFocus === "approvals") {
            return
        }
        if (view === "calendar") {
            setView("list")
            localStorage.setItem("tasks-view", "list")
        }
    }, [pendingFocus, view])

    useEffect(() => {
        if (!pendingFocus) return
        if (pendingFocus !== "approvals" && view !== "list") return
        if (isLoading) return
        if (pendingFocus === "approvals" && (loadingApprovals || loadingStatusRequests || loadingImportApprovals)) return

        const targetId =
            pendingFocus === "approvals"
                ? "tasks-approvals"
                : pendingFocus === "tasks"
                    ? "tasks-list"
                    : `tasks-${pendingFocus}`
        const target =
            document.getElementById(targetId) || document.getElementById("tasks-list")
        if (!target) return

        target.scrollIntoView({ behavior: "smooth", block: "start" })
        setPendingFocus(null)
    }, [pendingFocus, view, isLoading, loadingApprovals, loadingStatusRequests, loadingImportApprovals])

    useEffect(() => {
        const visibleIds = new Set((incompleteTasks?.items ?? []).map((task) => task.id))
        setSelectedTaskIds((prev) => {
            if (prev.size === 0) return prev
            let changed = false
            const next = new Set<string>()
            for (const taskId of prev) {
                if (visibleIds.has(taskId)) {
                    next.add(taskId)
                } else {
                    changed = true
                }
            }
            return changed ? next : prev
        })
    }, [incompleteTasks?.items])

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
                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading tasks...</span>
                    </Card>
                )}

                {/* Error State */}
                {!isLoading && hasError && (
                    <Card className="flex flex-col items-center justify-center gap-3 p-12 border-destructive/40 bg-destructive/5">
                        <span className="text-destructive">Unable to load tasks. Please try again.</span>
                        <Button variant="outline" size="sm" onClick={handleRetry}>
                            Retry
                        </Button>
                    </Card>
                )}

                {/* Calendar View */}
                {!isLoading && !hasError && view === "calendar" && (
                    <TasksCalendarView filter={filter} onTaskClick={handleTaskClick} />
                )}

                {/* Pending Approvals Section */}
                {!isLoading && !hasError && (
                    <TasksApprovalsSection
                        pendingApprovals={pendingApprovals?.items ?? []}
                        pendingStatusRequests={pendingStatusRequests?.items ?? []}
                        pendingImportApprovals={pendingImportApprovals ?? []}
                        loadingApprovals={loadingApprovals}
                        loadingStatusRequests={loadingStatusRequests}
                        loadingImportApprovals={loadingImportApprovals}
                        onResolvedStatusRequests={refetchStatusRequests}
                        onResolvedImportApprovals={refetchImportApprovals}
                        currentUserId={currentUserId}
                    />
                )}

                {/* List View */}
                {!isLoading && !hasError && view === "list" && (
                    <TasksListView
                        incompleteTasks={incompleteTasks?.items ?? []}
                        completedTasks={completedTasks ?? null}
                        selectedTaskIds={selectedTaskIds}
                        showCompleted={showCompleted}
                        loadingCompleted={loadingCompleted}
                        completedError={!!completedError}
                        onToggleShowCompleted={() => setShowCompleted((prev) => !prev)}
                        onTaskToggle={handleTaskToggle}
                        onTaskClick={handleTaskClick}
                        onSelectTask={handleSelectTask}
                        onSelectAll={handleSelectAllTasks}
                        onBulkCompleteSelected={handleBulkCompleteSelected}
                        bulkCompletePending={bulkCompleteTasks.isPending}
                    />
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
                        surrogate_id: editingTask.surrogate_id,
                    } : null}
                    open={!!editingTask}
                    onClose={() => setEditingTask(null)}
                    onSave={handleSaveTask}
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
