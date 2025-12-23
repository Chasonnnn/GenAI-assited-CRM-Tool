"use client"

/**
 * Match Tasks Calendar - Calendar view for tasks related to a matched Surrogate and IP
 * 
 * Features:
 * - Month/Week/Day view toggle
 * - Filter by All/Surrogate/IP
 * - Tasks color-coded by source (purple=Surrogate, green=IP)
 */

import { useState, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    ChevronLeftIcon,
    ChevronRightIcon,
    CheckSquareIcon,
    Loader2Icon,
    UserIcon,
    UsersIcon,
} from "lucide-react"
import { useTasks } from "@/lib/hooks/use-tasks"
import type { TaskListItem } from "@/lib/api/tasks"
import {
    format,
    startOfMonth,
    endOfMonth,
    startOfWeek,
    endOfWeek,
    eachDayOfInterval,
    isSameMonth,
    addMonths,
    subMonths,
    parseISO,
    isToday,
} from "date-fns"

// Colors
const SURROGATE_COLOR = "bg-purple-500"
const IP_COLOR = "bg-green-500"

type ViewType = "month" | "week" | "day"
type FilterType = "all" | "surrogate" | "ip"

interface MatchTasksCalendarProps {
    caseId: string
    ipId?: string
}

// Task Item Component
function TaskItem({
    task,
    source,
    compact = false,
}: {
    task: TaskListItem
    source: "surrogate" | "ip"
    compact?: boolean
}) {
    const color = source === "surrogate" ? SURROGATE_COLOR : IP_COLOR
    const time = task.due_time ? format(parseISO(`2000-01-01T${task.due_time}`), "h:mm a") : ""

    if (compact) {
        return (
            <div className={`w-full text-left px-2 py-1 rounded text-xs truncate ${color} text-white`}>
                {time && `${time} - `}📋 {task.title}
            </div>
        )
    }

    return (
        <div className={`w-full text-left p-2 rounded-lg border-l-4 ${source === "surrogate" ? "border-purple-500" : "border-green-500"} bg-muted/50`}>
            <p className="font-medium text-sm truncate flex items-center gap-1">
                <CheckSquareIcon className="size-3" />
                {task.title}
            </p>
            {time && <p className="text-xs text-muted-foreground">{time}</p>}
            <Badge variant="outline" className="text-xs mt-1">
                {source === "surrogate" ? "Surrogate" : "IP"}
            </Badge>
        </div>
    )
}

// Month View
function MonthView({
    currentDate,
    tasks,
    taskSources,
}: {
    currentDate: Date
    tasks: TaskListItem[]
    taskSources: Map<string, "surrogate" | "ip">
}) {
    const days = useMemo(() => {
        const monthStart = startOfMonth(currentDate)
        const monthEnd = endOfMonth(currentDate)
        const calendarStart = startOfWeek(monthStart)
        const calendarEnd = endOfWeek(monthEnd)
        return eachDayOfInterval({ start: calendarStart, end: calendarEnd })
    }, [currentDate])

    const tasksByDate = useMemo(() => {
        const map = new Map<string, TaskListItem[]>()
        tasks.forEach((task) => {
            if (!task.due_date) return
            const dateStr = task.due_date
            if (!map.has(dateStr)) map.set(dateStr, [])
            map.get(dateStr)!.push(task)
        })
        return map
    }, [tasks])

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            {/* Day Headers */}
            <div className="grid grid-cols-7 bg-muted">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
                    <div key={day} className="p-2 text-center text-sm font-medium text-muted-foreground border-b border-border">
                        {day}
                    </div>
                ))}
            </div>

            {/* Days Grid */}
            <div className="grid grid-cols-7">
                {days.map((day, i) => {
                    const dateStr = format(day, "yyyy-MM-dd")
                    const dayTasks = tasksByDate.get(dateStr) || []
                    const isCurrentMonth = isSameMonth(day, currentDate)
                    const isCurrentDay = isToday(day)

                    return (
                        <div
                            key={i}
                            className={`min-h-[80px] p-1 border-b border-r border-border ${!isCurrentMonth ? "bg-muted/30" : ""}`}
                        >
                            <div className={`text-sm p-1 ${isCurrentDay ? "bg-primary text-primary-foreground rounded-full w-7 h-7 flex items-center justify-center" : ""} ${!isCurrentMonth ? "text-muted-foreground" : ""}`}>
                                {format(day, "d")}
                            </div>
                            <div className="space-y-1 mt-1">
                                {dayTasks.slice(0, 2).map((task) => (
                                    <TaskItem
                                        key={task.id}
                                        task={task}
                                        source={taskSources.get(task.id) || "surrogate"}
                                        compact
                                    />
                                ))}
                                {dayTasks.length > 2 && (
                                    <p className="text-xs text-muted-foreground text-center">
                                        +{dayTasks.length - 2} more
                                    </p>
                                )}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

// Week View
function WeekView({
    currentDate,
    tasks,
    taskSources,
}: {
    currentDate: Date
    tasks: TaskListItem[]
    taskSources: Map<string, "surrogate" | "ip">
}) {
    const days = useMemo(() => {
        const weekStart = startOfWeek(currentDate)
        const weekEnd = endOfWeek(currentDate)
        return eachDayOfInterval({ start: weekStart, end: weekEnd })
    }, [currentDate])

    const tasksByDate = useMemo(() => {
        const map = new Map<string, TaskListItem[]>()
        tasks.forEach((task) => {
            if (!task.due_date) return
            if (!map.has(task.due_date)) map.set(task.due_date, [])
            map.get(task.due_date)!.push(task)
        })
        return map
    }, [tasks])

    return (
        <div className="grid grid-cols-7 gap-2">
            {days.map((day) => {
                const dateStr = format(day, "yyyy-MM-dd")
                const dayTasks = tasksByDate.get(dateStr) || []
                const isCurrentDay = isToday(day)

                return (
                    <div key={dateStr} className="border border-border rounded-lg overflow-hidden">
                        <div className={`p-2 text-center border-b ${isCurrentDay ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                            <p className="text-xs font-medium">{format(day, "EEE")}</p>
                            <p className="text-lg font-semibold">{format(day, "d")}</p>
                        </div>
                        <div className="p-2 space-y-2 min-h-[150px]">
                            {dayTasks.map((task) => (
                                <TaskItem
                                    key={task.id}
                                    task={task}
                                    source={taskSources.get(task.id) || "surrogate"}
                                />
                            ))}
                            {dayTasks.length === 0 && (
                                <p className="text-xs text-muted-foreground text-center py-4">No tasks</p>
                            )}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

// Day View
function DayView({
    currentDate,
    tasks,
    taskSources,
}: {
    currentDate: Date
    tasks: TaskListItem[]
    taskSources: Map<string, "surrogate" | "ip">
}) {
    const dateStr = format(currentDate, "yyyy-MM-dd")

    const dayTasks = useMemo(() => {
        return tasks
            .filter((task) => task.due_date === dateStr)
            .sort((a, b) => (a.due_time || "").localeCompare(b.due_time || ""))
    }, [dateStr, tasks])

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            <div className="p-3 bg-muted border-b border-border text-center">
                <p className="font-medium">{format(currentDate, "EEEE, MMMM d, yyyy")}</p>
            </div>
            <div className="p-4 space-y-2 min-h-[200px]">
                {dayTasks.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">No tasks for this day</p>
                ) : (
                    dayTasks.map((task) => (
                        <TaskItem
                            key={task.id}
                            task={task}
                            source={taskSources.get(task.id) || "surrogate"}
                        />
                    ))
                )}
            </div>
        </div>
    )
}

// Main Component
export function MatchTasksCalendar({ caseId, ipId }: MatchTasksCalendarProps) {
    const [currentDate, setCurrentDate] = useState(new Date())
    const [viewType, setViewType] = useState<ViewType>("month")
    const [filter, setFilter] = useState<FilterType>("all")

    // Fetch tasks for Surrogate case
    const { data: surrogateTasks, isLoading: loadingSurrogate } = useTasks({
        case_id: caseId,
        is_completed: false,
        per_page: 100,
    })

    // Fetch tasks for IP (now supported via intended_parent_id filter)
    const { data: ipTasks, isLoading: loadingIP } = useTasks({
        intended_parent_id: ipId || undefined,
        is_completed: false,
        per_page: 100,
    })

    // Build combined task list and source tracking
    const { allTasks, taskSources } = useMemo(() => {
        const sources = new Map<string, "surrogate" | "ip">()
        const tasks: TaskListItem[] = []

        // Add surrogate tasks
        if (surrogateTasks?.items) {
            surrogateTasks.items.forEach((task) => {
                sources.set(task.id, "surrogate")
                tasks.push(task)
            })
        }

        // Add IP tasks
        if (ipTasks?.items) {
            ipTasks.items.forEach((task) => {
                // Avoid duplicates (a task could theoretically have both case_id and intended_parent_id)
                if (!sources.has(task.id)) {
                    sources.set(task.id, "ip")
                    tasks.push(task)
                }
            })
        }

        // Filter based on selection
        let filtered = tasks
        if (filter === "surrogate") {
            filtered = tasks.filter((t) => sources.get(t.id) === "surrogate")
        } else if (filter === "ip") {
            filtered = tasks.filter((t) => sources.get(t.id) === "ip")
        }

        return { allTasks: filtered, taskSources: sources }
    }, [surrogateTasks, ipTasks, filter])

    // Navigation
    const navigate = (direction: "prev" | "next") => {
        if (viewType === "month") {
            setCurrentDate(direction === "prev" ? subMonths(currentDate, 1) : addMonths(currentDate, 1))
        } else if (viewType === "week") {
            const days = direction === "prev" ? -7 : 7
            setCurrentDate(new Date(currentDate.getTime() + days * 24 * 60 * 60 * 1000))
        } else {
            const days = direction === "prev" ? -1 : 1
            setCurrentDate(new Date(currentDate.getTime() + days * 24 * 60 * 60 * 1000))
        }
    }

    const isLoading = loadingSurrogate || loadingIP

    return (
        <div className="space-y-4">
            {/* Header with navigation and filters */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => navigate("prev")}>
                        <ChevronLeftIcon className="size-4" />
                    </Button>
                    <h2 className="text-base font-semibold min-w-[160px] text-center">
                        {viewType === "month" && format(currentDate, "MMMM yyyy")}
                        {viewType === "week" && `Week of ${format(startOfWeek(currentDate), "MMM d")}`}
                        {viewType === "day" && format(currentDate, "MMM d, yyyy")}
                    </h2>
                    <Button variant="outline" size="sm" onClick={() => navigate("next")}>
                        <ChevronRightIcon className="size-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setCurrentDate(new Date())}>
                        Today
                    </Button>
                </div>

                <div className="flex items-center gap-2">
                    {/* Filter */}
                    <div className="flex gap-1 border rounded-lg p-1">
                        <Button
                            variant={filter === "all" ? "secondary" : "ghost"}
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => setFilter("all")}
                        >
                            All
                        </Button>
                        <Button
                            variant={filter === "surrogate" ? "secondary" : "ghost"}
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => setFilter("surrogate")}
                        >
                            <UserIcon className="size-3 mr-1" />
                            Surrogate
                        </Button>
                        <Button
                            variant={filter === "ip" ? "secondary" : "ghost"}
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => setFilter("ip")}
                        >
                            <UsersIcon className="size-3 mr-1" />
                            IP
                        </Button>
                    </div>

                    {/* View selector */}
                    <Select value={viewType} onValueChange={(v) => v && setViewType(v as ViewType)}>
                        <SelectTrigger className="w-24 h-8">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="month">Month</SelectItem>
                            <SelectItem value="week">Week</SelectItem>
                            <SelectItem value="day">Day</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Calendar Content */}
            {isLoading ? (
                <div className="py-12 flex items-center justify-center">
                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <>
                    {viewType === "month" && (
                        <MonthView
                            currentDate={currentDate}
                            tasks={allTasks}
                            taskSources={taskSources}
                        />
                    )}
                    {viewType === "week" && (
                        <WeekView
                            currentDate={currentDate}
                            tasks={allTasks}
                            taskSources={taskSources}
                        />
                    )}
                    {viewType === "day" && (
                        <DayView
                            currentDate={currentDate}
                            tasks={allTasks}
                            taskSources={taskSources}
                        />
                    )}
                </>
            )}

            {/* Legend */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-purple-500"></div>
                    <span>Surrogate Tasks</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-green-500"></div>
                    <span>IP Tasks</span>
                </div>
            </div>
        </div>
    )
}
