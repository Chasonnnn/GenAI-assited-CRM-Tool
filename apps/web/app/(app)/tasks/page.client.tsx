"use client"

/**
 * Tasks Page - /tasks
 * 
 * Unified view showing tasks and appointments with list/calendar toggle.
 */

import { startTransition, useState, useEffect, useRef } from "react"
import type { Route } from "next"
import { useSearchParams, useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PlusIcon, Loader2Icon, ListIcon, CalendarIcon } from "lucide-react"
import { TasksCalendarView } from "@/components/tasks/TasksCalendarView"
import { TasksListView } from "@/components/tasks/TasksListView"
import { TasksApprovalsSection } from "@/components/tasks/TasksApprovalsSection"
import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import { AddTaskDialog, type TaskFormData } from "@/components/tasks/AddTaskDialog"
import { useTasks, useCompleteTask, useUncompleteTask, useUpdateTask, useCreateTask, useCreateTaskBatch, useDeleteTask, useBulkCompleteTasks } from "@/lib/hooks/use-tasks"
import { useStatusChangeRequests } from "@/lib/hooks/use-status-change-requests"
import { usePendingImportApprovals } from "@/lib/hooks/use-import"
import { useAuth } from "@/lib/auth-context"
import { useAIContext } from "@/lib/context/ai-context"
import type { TaskListItem } from "@/lib/types/task"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"
import { format, parseISO } from "date-fns"
import { toast } from "@/components/ui/toast"

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

function useTasksPageController() {
    const searchParams = useSearchParams()
    const { replace } = useRouter()
    const { user: currentUser } = useAuth()
    const canApproveImports = ["admin", "developer"].includes(currentUser?.role || "")
    const currentUserId = currentUser?.user_id ?? null

    // Read initial values from URL params
    const urlFilter = searchParams.get("filter")
    const urlFocus = searchParams.get("focus")
    const urlOwnerId = searchParams.get("owner_id")
    const canViewOtherOwners = ["admin", "developer"].includes(currentUser?.role || "")
    const ownerOverride = canViewOtherOwners && urlOwnerId ? urlOwnerId : null
    const focusTarget = isFocusTarget(urlFocus) ? urlFocus : null
    const handledFocusRef = useRef<FocusTarget | null>(null)

    const [filter, setFilter] = useState<FilterType>(
        isFilterType(urlFilter) ? urlFilter : "my_tasks"
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
    const [manualViewFocusTarget, setManualViewFocusTarget] = useState<FocusTarget | null>(null)

    useEffect(() => {
        if (!focusTarget) {
            handledFocusRef.current = null
        }
    }, [focusTarget])

    const focusRequiresListView = focusTarget !== null && focusTarget !== "approvals"
    const shouldUseListViewForFocus =
        focusRequiresListView && manualViewFocusTarget !== focusTarget
    const activeView = shouldUseListViewForFocus ? "list" : view

    // Sync state changes back to URL
    const updateUrlParams = (filterValue: FilterType) => {
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
        replace(newUrl as Route, { scroll: false })
    }

    // Handle filter change
    const handleFilterChange = (newFilter: FilterType) => {
        setFilter(newFilter)
        updateUrlParams(newFilter)
    }

    const handleViewChange = (newView: ViewType) => {
        if (focusTarget) {
            setManualViewFocusTarget(focusTarget)
        }
        setView(newView)
        localStorage.setItem("tasks-view", newView)
    }

    // Create/edit modal state
    const [addTaskDialogOpen, setAddTaskDialogOpen] = useState(false)
    const [editingTask, setEditingTask] = useState<TaskListItem | null>(null)

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
    const createTaskBatch = useCreateTaskBatch()
    const deleteTask = useDeleteTask()

    const { setContext: setAIContext, clearContext: clearAIContext } = useAIContext()

    const handleTaskClick = (task: TaskListItem) => {
        setAIContext({
            entityType: "task",
            entityId: task.id,
            entityName: task.title,
        })
        setEditingTask(task)
    }

    const handleCloseEditModal = () => {
        setEditingTask(null)
        clearAIContext()
    }

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

    const handleSelectTask = (taskId: string, selected: boolean) => {
        setSelectedTaskIds((prev) => {
            const next = new Set(prev)
            if (selected) {
                next.add(taskId)
            } else {
                next.delete(taskId)
            }
            return next
        })
    }

    const handleSelectAllTasks = (selected: boolean) => {
        if (!selected) {
            setSelectedTaskIds(new Set())
            return
        }
        const visibleTaskIds = (incompleteTasks?.items ?? []).map((task) => task.id)
        setSelectedTaskIds(new Set(visibleTaskIds))
    }

    const handleBulkCompleteSelected = async () => {
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
    }

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

        await createTaskBatch.mutateAsync(dates.map((date) => buildPayload(format(date, "yyyy-MM-dd"))))
    }

    const isLoading = loadingIncomplete
    const hasError = incompleteError || completedError
    const handleRetry = () => {
        void refetchIncomplete()
        void refetchCompleted()
    }

    useEffect(() => {
        if (!focusTarget || handledFocusRef.current === focusTarget) return
        if (focusTarget !== "approvals" && activeView !== "list") return
        if (isLoading) return
        if (focusTarget === "approvals" && (loadingApprovals || loadingStatusRequests || loadingImportApprovals)) return

        const targetId =
            focusTarget === "approvals"
                ? "tasks-approvals"
                : focusTarget === "tasks"
                    ? "tasks-list"
                    : `tasks-${focusTarget}`
        const target =
            document.getElementById(targetId) || document.getElementById("tasks-list")
        if (!target) return

        target.scrollIntoView({ behavior: "smooth", block: "start" })
        if (focusTarget !== "approvals") {
            localStorage.setItem("tasks-view", "list")
        }
        handledFocusRef.current = focusTarget
    }, [focusTarget, activeView, isLoading, loadingApprovals, loadingStatusRequests, loadingImportApprovals])

    useEffect(() => {
        const visibleIds = new Set((incompleteTasks?.items ?? []).map((task) => task.id))
        startTransition(() => {
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
        })
    }, [incompleteTasks?.items])

    return {
        addTaskDialogOpen,
        addTaskPending: createTask.isPending || createTaskBatch.isPending,
        completedError: !!completedError,
        completedTasks: completedTasks ?? null,
        currentUserId,
        deleteTaskPending: deleteTask.isPending,
        editModalTask: editingTask ? {
            id: editingTask.id,
            title: editingTask.title,
            description: editingTask.description ?? null,
            task_type: editingTask.task_type,
            due_date: editingTask.due_date,
            due_time: editingTask.due_time ?? null,
            is_completed: editingTask.is_completed,
            surrogate_id: editingTask.surrogate_id,
        } : null,
        filter,
        hasError,
        incompleteTasks: incompleteTasks?.items ?? [],
        isLoading,
        loadingApprovals,
        loadingCompleted,
        loadingImportApprovals,
        loadingStatusRequests,
        pendingApprovals: pendingApprovals?.items ?? [],
        pendingImportApprovals: pendingImportApprovals ?? [],
        pendingStatusRequests: pendingStatusRequests?.items ?? [],
        selectedTaskIds,
        showCompleted,
        view: activeView,
        bulkCompletePending: bulkCompleteTasks.isPending,
        handleAddTask,
        handleBulkCompleteSelected,
        handleDeleteTask,
        handleFilterChange,
        handleRetry,
        handleSaveTask,
        handleSelectAllTasks,
        handleSelectTask,
        handleTaskClick,
        handleTaskToggle,
        handleViewChange,
        onCloseEditModal: handleCloseEditModal,
        onOpenAddTaskDialog: () => setAddTaskDialogOpen(true),
        refetchImportApprovals,
        refetchStatusRequests,
        setAddTaskDialogOpen,
        toggleShowCompleted: () => setShowCompleted((prev) => !prev),
    }
}

type TasksPageController = ReturnType<typeof useTasksPageController>

function TasksPageHeader({ controller }: { controller: TasksPageController }) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <h1 className="text-2xl font-semibold">Tasks</h1>
                <Button onClick={controller.onOpenAddTaskDialog}>
                    <PlusIcon className="mr-2 size-4" />
                    Add Task
                </Button>
            </div>
        </div>
    )
}

function TasksPageControls({ controller }: { controller: TasksPageController }) {
    return (
        <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
                <Button
                    variant={controller.filter === "my_tasks" ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => controller.handleFilterChange("my_tasks")}
                >
                    My Tasks
                </Button>
                <Button
                    variant={controller.filter === "all" ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => controller.handleFilterChange("all")}
                >
                    All Tasks
                </Button>
            </div>

            <div className="flex gap-1 border rounded-lg p-1">
                <Button
                    variant={controller.view === "list" ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => controller.handleViewChange("list")}
                >
                    <ListIcon className="size-4 mr-1" />
                    List
                </Button>
                <Button
                    variant={controller.view === "calendar" ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => controller.handleViewChange("calendar")}
                >
                    <CalendarIcon className="size-4 mr-1" />
                    Calendar
                </Button>
            </div>
        </div>
    )
}

function TasksPageContent({ controller }: { controller: TasksPageController }) {
    const canShowTaskViews = !controller.isLoading && !controller.hasError

    return (
        <div className="flex-1 p-6 space-y-6">
            <p className="text-sm text-muted-foreground">
                Manage your tasks and appointments in one unified view.
            </p>

            <TasksPageControls controller={controller} />

            {controller.isLoading && (
                <Card className="flex items-center justify-center p-12">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading tasks…</span>
                </Card>
            )}

            {!controller.isLoading && controller.hasError && (
                <Card className="flex flex-col items-center justify-center gap-3 p-12 border-destructive/40 bg-destructive/5">
                    <span className="text-destructive">Unable to load tasks. Please try again.</span>
                    <Button variant="outline" size="sm" onClick={controller.handleRetry}>
                        Retry
                    </Button>
                </Card>
            )}

            {canShowTaskViews && controller.view === "calendar" && (
                <TasksCalendarView
                    filter={controller.filter}
                    onTaskClick={controller.handleTaskClick}
                />
            )}

            {canShowTaskViews && (
                <TasksApprovalsSection
                    pendingApprovals={controller.pendingApprovals}
                    pendingStatusRequests={controller.pendingStatusRequests}
                    pendingImportApprovals={controller.pendingImportApprovals}
                    loadingApprovals={controller.loadingApprovals}
                    loadingStatusRequests={controller.loadingStatusRequests}
                    loadingImportApprovals={controller.loadingImportApprovals}
                    onResolvedStatusRequests={controller.refetchStatusRequests}
                    onResolvedImportApprovals={controller.refetchImportApprovals}
                    currentUserId={controller.currentUserId}
                />
            )}

            {canShowTaskViews && controller.view === "list" && (
                <TasksListView
                    incompleteTasks={controller.incompleteTasks}
                    completedTasks={controller.completedTasks}
                    selectedTaskIds={controller.selectedTaskIds}
                    showCompleted={controller.showCompleted}
                    loadingCompleted={controller.loadingCompleted}
                    completedError={controller.completedError}
                    onToggleShowCompleted={controller.toggleShowCompleted}
                    onTaskToggle={controller.handleTaskToggle}
                    onTaskClick={controller.handleTaskClick}
                    onSelectTask={controller.handleSelectTask}
                    onSelectAll={controller.handleSelectAllTasks}
                    onBulkCompleteSelected={controller.handleBulkCompleteSelected}
                    bulkCompletePending={controller.bulkCompletePending}
                />
            )}

            <TasksPageDialogs controller={controller} />
        </div>
    )
}

function TasksPageDialogs({ controller }: { controller: TasksPageController }) {
    return (
        <>
            <TaskEditModal
                task={controller.editModalTask}
                open={!!controller.editModalTask}
                onClose={controller.onCloseEditModal}
                onSave={controller.handleSaveTask}
                onDelete={controller.handleDeleteTask}
                isDeleting={controller.deleteTaskPending}
            />
            <AddTaskDialog
                open={controller.addTaskDialogOpen}
                onOpenChange={controller.setAddTaskDialogOpen}
                onSubmit={controller.handleAddTask}
                isPending={controller.addTaskPending}
            />
        </>
    )
}

export default function TasksPage() {
    const controller = useTasksPageController()

    return (
        <div className="flex min-h-screen flex-col">
            <TasksPageHeader controller={controller} />
            <TasksPageContent controller={controller} />
        </div>
    )
}
