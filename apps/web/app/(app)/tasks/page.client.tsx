"use client"

/**
 * Tasks Page - /tasks
 * 
 * Unified view showing tasks and appointments with list/calendar toggle.
 */

import { useState, type ReactNode } from "react"
import type { Route } from "next"
import { useSearchParams, useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PlusIcon, Loader2Icon, ListIcon, CalendarDaysIcon } from "lucide-react"
import { ListToolbar, ListToolbarSearch } from "@/components/list-toolbar"
import { PageHeader } from "@/components/page-header"
import { QueryErrorState } from "@/components/error-state"
import { SegmentedToggle } from "@/components/appointments/SegmentedToggle"
import { TasksCalendarView } from "@/components/tasks/TasksCalendarView"
import { TasksListView } from "@/components/tasks/TasksListView"
import { TasksApprovalsSection } from "@/components/tasks/TasksApprovalsSection"
import { TaskDetailDialog } from "@/components/tasks/TaskDetailDialog"
import { AddTaskDialog, type TaskFormData } from "@/components/tasks/AddTaskDialog"
import { useTasks, useCompleteTask, useUncompleteTask, useUpdateTask, useCreateTask, useCreateTaskBatch, useDeleteTask, useBulkCompleteTasks } from "@/lib/hooks/use-tasks"
import { useStatusChangeRequests } from "@/lib/hooks/use-status-change-requests"
import { usePendingImportApprovals } from "@/lib/hooks/use-import"
import { useAssignees } from "@/lib/hooks/use-surrogates"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { useTaskFocusNavigation } from "@/lib/hooks/use-task-focus-navigation"
import type { UnifiedCalendarTaskFilter } from "@/lib/hooks/use-unified-calendar-data"
import { useAuth } from "@/lib/auth-context"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { useAIContext } from "@/lib/context/ai-context"
import type { TaskListItem } from "@/lib/types/task"
import type { TaskLinkedType, TaskListParams, TaskUpdatePayload } from "@/lib/api/tasks"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import {
    getTaskDueFilterLabel,
    getTaskLinkedTypeLabel,
    getTaskStatusFilterLabel,
    isTaskDueFilter,
    isTaskLinkedType,
    isTaskStatusFilter,
    TASK_DUE_FILTER_OPTIONS,
    TASK_LINKED_TYPE_OPTIONS,
    TASK_STATUS_FILTER_OPTIONS,
    type TaskDueFilter,
    type TaskStatusFilter,
} from "@/lib/task-labels"
import { formatLocalDate, startOfLocalDay } from "@/lib/utils/date"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"
import { addDays, format, parseISO } from "date-fns"
import { toast } from "@/components/ui/toast"
import { showUndoToast } from "@/components/ui/undo-toast"

type FilterType = "all" | "my_tasks"
const isFilterType = (value: string | null): value is FilterType =>
    value === "all" || value === "my_tasks"

type ViewType = "list" | "calendar"
const isViewType = (value: string | null): value is ViewType =>
    value === "list" || value === "calendar"

const SCOPE_OPTIONS = [
    { value: "my_tasks", label: "My Tasks" },
    { value: "all", label: "All Tasks" },
] as const satisfies ReadonlyArray<{ value: FilterType; label: string }>

const VIEW_OPTIONS = [
    { value: "list", label: "List", icon: <ListIcon className="size-4" aria-hidden="true" /> },
    { value: "calendar", label: "Calendar", icon: <CalendarDaysIcon className="size-4" aria-hidden="true" /> },
] as const satisfies ReadonlyArray<{ value: ViewType; label: string; icon: ReactNode }>

// Below sm two filters share a row; the min width makes them wrap instead of shrinking beside the toggles.
const FILTER_TRIGGER_CLASS =
    "min-w-[calc(50%-0.375rem)] flex-1 bg-background sm:w-[170px] sm:min-w-0 sm:flex-none"

/** Due window for the Due filter, using the same day boundaries as the list sections. */
function getDueParams(due: TaskDueFilter): Pick<TaskListParams, "due_before" | "due_after"> {
    const today = startOfLocalDay()
    if (due === "overdue") return { due_before: formatLocalDate(addDays(today, -1)) }
    if (due === "today") return { due_after: formatLocalDate(today), due_before: formatLocalDate(today) }
    if (due === "week") return { due_after: formatLocalDate(today), due_before: formatLocalDate(addDays(today, 7)) }
    return {}
}

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
    // Notification links open one task (?task=) or point at one approval (?approval=).
    const urlTaskId = searchParams.get("task")
    const urlApprovalId = searchParams.get("approval")
    const canViewOtherOwners = ["admin", "developer"].includes(currentUser?.role || "")
    const ownerOverride = canViewOtherOwners && urlOwnerId ? urlOwnerId : null
    const focusTarget = isFocusTarget(urlFocus) ? urlFocus : null

    const [filter, setFilter] = useState<FilterType>(
        isFilterType(urlFilter) ? urlFilter : "my_tasks"
    )
    const [status, setStatus] = useState<TaskStatusFilter>("open")
    const [due, setDue] = useState<TaskDueFilter>("all")
    const [linkedType, setLinkedType] = useState<TaskLinkedType | "all">("all")
    // Same gates as the sidebar: a viewer only filters by record types they can open.
    const { can } = usePermissionCheck()
    const linkedTypeOptions = TASK_LINKED_TYPE_OPTIONS.filter((option) =>
        option.value === "intended_parent"
            ? can("view_intended_parents")
            : option.value === "donor"
              ? can("view_donors")
              : true,
    )
    const [search, setSearch] = useState("")
    const debouncedSearch = useDebouncedValue(search.trim(), 300)
    const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set())
    const [view, setView] = useState<ViewType>(() => {
        if (typeof window !== "undefined") {
            const stored = localStorage.getItem("tasks-view")
            return isViewType(stored) ? stored : "calendar"
        }
        return "calendar"
    })
    const [manualViewFocusTarget, setManualViewFocusTarget] = useState<FocusTarget | null>(null)

    const focusRequiresListView = focusTarget !== null && focusTarget !== "approvals"
    const shouldUseListViewForFocus =
        focusRequiresListView && manualViewFocusTarget !== focusTarget
    const activeView = shouldUseListViewForFocus ? "list" : view

    // Sync scope and assignee back to the URL; dashboard links open the page with them set.
    const updateUrlParams = (filterValue: FilterType, ownerId: string | null) => {
        const newParams = new URLSearchParams(searchParams.toString())
        if (filterValue !== "my_tasks") {
            newParams.set("filter", filterValue)
        } else {
            newParams.delete("filter")
        }
        if (ownerId) {
            newParams.set("owner_id", ownerId)
        } else {
            newParams.delete("owner_id")
        }
        const nextQuery = newParams.toString()
        const currentQuery = searchParams.toString()
        if (nextQuery === currentQuery) return
        const newUrl = nextQuery ? `/tasks?${nextQuery}` : "/tasks"
        const currentUrl = currentQuery ? `/tasks?${currentQuery}` : "/tasks"
        if (newUrl === currentUrl) return
        replace(newUrl as Route, { scroll: false })
    }

    // My Tasks clears the assignee; an assignee implies All Tasks.
    const handleFilterChange = (newFilter: FilterType) => {
        setSelectedTaskIds(new Set())
        setFilter(newFilter)
        updateUrlParams(newFilter, newFilter === "my_tasks" ? null : ownerOverride)
    }

    const handleAssigneeChange = (ownerId: string | null) => {
        setSelectedTaskIds(new Set())
        if (ownerId) setFilter("all")
        updateUrlParams(ownerId ? "all" : filter, ownerId)
    }

    const resetFilters = () => {
        setStatus("open")
        setDue("all")
        setLinkedType("all")
        setSearch("")
        if (ownerOverride) handleAssigneeChange(null)
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

    const handleSaveTask = async (taskId: string, data: TaskUpdatePayload) => {
        await updateTask.mutateAsync({ taskId, data })
    }

    const handleDeleteTask = async (taskId: string) => {
        await deleteTask.mutateAsync(taskId)
        setEditingTask(null)
    }

    const taskOwnerId = ownerOverride ?? undefined
    const useMyTasks = !taskOwnerId && filter === "my_tasks"
    const ownerParams = taskOwnerId ? { owner_id: taskOwnerId } : {}
    const isListView = activeView === "list"

    // Search and linked type apply to both views; the calendar has its own date navigation, so
    // the Due filter applies to the list only.
    const recordFilters: Pick<TaskListParams, "q" | "linked_type"> = {
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
        ...(linkedType !== "all" ? { linked_type: linkedType } : {}),
    }
    const listParams: TaskListParams = {
        my_tasks: useMyTasks,
        ...ownerParams,
        ...recordFilters,
        ...getDueParams(due),
        exclude_approvals: true,
    }
    const calendarTaskFilter: UnifiedCalendarTaskFilter = {
        my_tasks: useMyTasks,
        ...ownerParams,
        ...recordFilters,
        is_completed: status === "all" ? null : status === "completed",
    }

    const {
        data: incompleteTasks,
        isLoading: loadingIncomplete,
        isError: incompleteError,
        error: incompleteQueryError,
        refetch: refetchIncomplete,
        isFetching: fetchingIncomplete,
    } = useTasks(
        { ...listParams, is_completed: false, per_page: 100 },
        { enabled: isListView && status !== "completed" },
    )

    const {
        data: completedTasks,
        isLoading: loadingCompleted,
        isError: completedError,
        error: completedQueryError,
        refetch: refetchCompleted,
        isFetching: fetchingCompleted,
    } = useTasks(
        { ...listParams, is_completed: true, per_page: 50 },
        { enabled: isListView && status !== "open" },
    )

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

    const visibleTaskIds = new Set((incompleteTasks?.items ?? []).map((task) => task.id))
    const visibleSelectedTaskIds = new Set<string>()
    for (const taskId of selectedTaskIds) {
        if (visibleTaskIds.has(taskId)) {
            visibleSelectedTaskIds.add(taskId)
        }
    }

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
        if (urlTaskId) {
            const nextParams = new URLSearchParams(searchParams.toString())
            nextParams.delete("task")
            const nextQuery = nextParams.toString()
            replace((nextQuery ? `/tasks?${nextQuery}` : "/tasks") as Route, { scroll: false })
        }
    }

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        setSelectedTaskIds((prev) => {
            if (!prev.has(taskId)) return prev
            const next = new Set(prev)
            next.delete(taskId)
            return next
        })
        try {
            if (isCompleted) {
                await uncompleteTask.mutateAsync(taskId)
                return
            }
            await completeTask.mutateAsync(taskId)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't update task. Try again.")
            if (message) toast.error(message)
            return
        }
        showUndoToast("Task completed", () => uncompleteTask.mutateAsync(taskId))
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
        const taskIds = Array.from(visibleSelectedTaskIds)
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
            ...(data.surrogate_id ? { surrogate_id: data.surrogate_id } : {}),
            ...(data.intended_parent_id ? { intended_parent_id: data.intended_parent_id } : {}),
            ...(data.donor_id ? { donor_id: data.donor_id } : {}),
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

    // With Status "All" the open list gates the view and the completed section loads on its own.
    const isLoading = isListView && (status === "completed" ? loadingCompleted : loadingIncomplete)
    const hasError = isListView && (status === "completed" ? completedError : incompleteError)
    const listError = status === "completed" ? completedQueryError : incompleteQueryError
    const isRetryingList = status === "completed" ? fetchingCompleted : fetchingIncomplete
    const handleRetry = () => {
        if (status !== "completed") void refetchIncomplete()
        if (status !== "open") void refetchCompleted()
    }

    const canFilterByAssignee = canViewOtherOwners
    const { data: assignees } = useAssignees({ enabled: canFilterByAssignee })
    const getAssigneeLabel = (value: string | null | undefined) => {
        if (!value || value === "all") return "All Assignees"
        return assignees?.find((assignee) => assignee.id === value)?.name ?? "Unknown assignee"
    }
    const hasFilters =
        search.trim() !== ""
        || linkedType !== "all"
        || (isListView && due !== "all")
        || ownerOverride !== null

    useTaskFocusNavigation({
        focusTarget,
        highlightedApprovalId: urlApprovalId,
        activeView,
        isLoading,
        loadingApprovals,
        loadingStatusRequests,
        loadingImportApprovals,
    })

    return {
        addTaskDialogOpen,
        addTaskPending: createTask.isPending || createTaskBatch.isPending,
        assigneeOptions: (assignees ?? []).map((assignee) => ({ value: assignee.id, label: assignee.name })),
        calendarTaskFilter,
        canFilterByAssignee,
        completedError: !!completedError,
        completedTasks: completedTasks?.items ?? [],
        completedTotal: completedTasks?.total ?? completedTasks?.items.length ?? 0,
        currentUserId,
        deleteTaskPending: deleteTask.isPending,
        due,
        editingTaskId: editingTask?.id ?? urlTaskId,
        highlightedApprovalId: urlApprovalId,
        filter,
        getAssigneeLabel,
        hasError,
        hasFilters,
        incompleteTasks: incompleteTasks?.items ?? [],
        isLoading,
        isRetryingList,
        linkedType,
        linkedTypeOptions,
        listError,
        loadingApprovals,
        loadingCompleted,
        loadingImportApprovals,
        loadingStatusRequests,
        ownerId: ownerOverride,
        pendingApprovals: pendingApprovals?.items ?? [],
        pendingImportApprovals: pendingImportApprovals ?? [],
        pendingStatusRequests: pendingStatusRequests?.items ?? [],
        search,
        selectedTaskIds: visibleSelectedTaskIds,
        status,
        view: activeView,
        bulkCompletePending: bulkCompleteTasks.isPending,
        handleAddTask,
        handleAssigneeChange,
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
        refetchCompleted: () => { void refetchCompleted() },
        refetchImportApprovals,
        refetchStatusRequests,
        resetFilters,
        setAddTaskDialogOpen,
        setDue,
        setLinkedType,
        setSearch,
        setStatus,
    }
}

type TasksPageController = ReturnType<typeof useTasksPageController>

function TasksPageToolbar({ controller }: { controller: TasksPageController }) {
    const isListView = controller.view === "list"

    return (
        <ListToolbar
            filters={
                <>
                    <SegmentedToggle
                        aria-label="Task scope"
                        value={controller.filter}
                        onValueChange={controller.handleFilterChange}
                        options={SCOPE_OPTIONS}
                    />
                    <SegmentedToggle
                        aria-label="Tasks view"
                        value={controller.view}
                        onValueChange={controller.handleViewChange}
                        options={VIEW_OPTIONS}
                        iconOnlyOnMobile
                    />
                    <Select
                        value={controller.status}
                        onValueChange={(value) => controller.setStatus(isTaskStatusFilter(value) ? value : "open")}
                    >
                        <SelectTrigger aria-label="Filter by status" className={FILTER_TRIGGER_CLASS}>
                            <SelectValue placeholder="Open">{getTaskStatusFilterLabel}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {TASK_STATUS_FILTER_OPTIONS.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {isListView ? (
                        <Select
                            value={controller.due}
                            onValueChange={(value) => controller.setDue(isTaskDueFilter(value) ? value : "all")}
                        >
                            <SelectTrigger aria-label="Filter by due date" className={FILTER_TRIGGER_CLASS}>
                                <SelectValue placeholder="Any Due Date">{getTaskDueFilterLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">Any Due Date</SelectItem>
                                {TASK_DUE_FILTER_OPTIONS.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    ) : null}
                    <Select
                        value={controller.linkedType}
                        onValueChange={(value) => controller.setLinkedType(isTaskLinkedType(value) ? value : "all")}
                    >
                        <SelectTrigger aria-label="Filter by linked record" className={FILTER_TRIGGER_CLASS}>
                            <SelectValue placeholder="All Records">{getTaskLinkedTypeLabel}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Records</SelectItem>
                            {controller.linkedTypeOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {controller.canFilterByAssignee ? (
                        <Select
                            value={controller.ownerId ?? "all"}
                            onValueChange={(value) =>
                                controller.handleAssigneeChange(typeof value === "string" && value !== "all" ? value : null)
                            }
                        >
                            <SelectTrigger aria-label="Filter by assignee" className={FILTER_TRIGGER_CLASS}>
                                <SelectValue placeholder="All Assignees">{controller.getAssigneeLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Assignees</SelectItem>
                                {controller.assigneeOptions.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    ) : null}
                </>
            }
            search={
                <ListToolbarSearch
                    value={controller.search}
                    onValueChange={controller.setSearch}
                    placeholder="Search tasks"
                    aria-label="Search tasks"
                />
            }
            chips={[
                controller.status !== "open" && {
                    key: "status",
                    label: `Status: ${getTaskStatusFilterLabel(controller.status)}`,
                    onRemove: () => controller.setStatus("open"),
                },
                isListView && controller.due !== "all" && {
                    key: "due",
                    label: `Due: ${getTaskDueFilterLabel(controller.due)}`,
                    onRemove: () => controller.setDue("all"),
                },
                controller.linkedType !== "all" && {
                    key: "linked",
                    label: `Linked: ${getTaskLinkedTypeLabel(controller.linkedType)}`,
                    onRemove: () => controller.setLinkedType("all"),
                },
                controller.ownerId !== null && {
                    key: "assignee",
                    label: `Assignee: ${controller.getAssigneeLabel(controller.ownerId)}`,
                    onRemove: () => controller.handleAssigneeChange(null),
                },
                controller.search.trim() !== "" && {
                    key: "search",
                    label: `Search: ${controller.search.trim()}`,
                    onRemove: () => controller.setSearch(""),
                },
            ]}
            onReset={controller.resetFilters}
        />
    )
}

function TasksPageContent({ controller }: { controller: TasksPageController }) {
    const canShowTaskViews = !controller.isLoading && !controller.hasError

    return (
        <div className="flex-1 space-y-6 p-6">
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
                highlightedId={controller.highlightedApprovalId}
            />

            {controller.isLoading && (
                <Card className="flex items-center justify-center p-12">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading tasks…</span>
                </Card>
            )}

            {!controller.isLoading && controller.hasError && (
                <QueryErrorState
                    error={controller.listError}
                    onRetry={controller.handleRetry}
                    isRetrying={controller.isRetryingList}
                    title="Couldn't load tasks"
                    headingLevel={2}
                />
            )}

            {canShowTaskViews && controller.view === "calendar" && (
                <TasksCalendarView
                    taskFilter={controller.calendarTaskFilter}
                    onTaskClick={controller.handleTaskClick}
                />
            )}

            {canShowTaskViews && controller.view === "list" && (
                <TasksListView
                    status={controller.status}
                    incompleteTasks={controller.incompleteTasks}
                    completedTasks={controller.completedTasks}
                    completedTotal={controller.completedTotal}
                    loadingCompleted={controller.loadingCompleted}
                    completedError={controller.completedError}
                    onRetryCompleted={controller.refetchCompleted}
                    selectedTaskIds={controller.selectedTaskIds}
                    onTaskToggle={controller.handleTaskToggle}
                    onTaskClick={controller.handleTaskClick}
                    onSelectTask={controller.handleSelectTask}
                    onSelectAll={controller.handleSelectAllTasks}
                    onBulkCompleteSelected={controller.handleBulkCompleteSelected}
                    bulkCompletePending={controller.bulkCompletePending}
                    onClearFilters={controller.hasFilters ? controller.resetFilters : null}
                />
            )}

            <TasksPageDialogs controller={controller} />
        </div>
    )
}

function TasksPageDialogs({ controller }: { controller: TasksPageController }) {
    return (
        <>
            {controller.editingTaskId ? <TaskDetailDialog
                taskId={controller.editingTaskId}
                onClose={controller.onCloseEditModal}
                onSave={controller.handleSaveTask}
                onDelete={controller.handleDeleteTask}
                isDeleting={controller.deleteTaskPending}
            /> : null}
            {controller.addTaskDialogOpen ? (
                <AddTaskDialog
                    open
                    onOpenChange={controller.setAddTaskDialogOpen}
                    onSubmit={controller.handleAddTask}
                    isPending={controller.addTaskPending}
                />
            ) : null}
        </>
    )
}

export default function TasksPage() {
    const controller = useTasksPageController()

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader
                title="Tasks"
                actions={
                    <Button onClick={controller.onOpenAddTaskDialog}>
                        <PlusIcon className="size-4" aria-hidden="true" />
                        Add task
                    </Button>
                }
            />
            <TasksPageToolbar controller={controller} />
            <TasksPageContent controller={controller} />
        </div>
    )
}
