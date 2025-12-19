"use client"

import { useState } from "react"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PlusIcon, LoaderIcon } from "lucide-react"
import { useTasks, useCompleteTask, useUncompleteTask } from "@/lib/hooks/use-tasks"
import type { TaskListItem } from "@/lib/types/task"

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
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

// Check if task is due tomorrow
function isDueTomorrow(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = new Date(dueDate)
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return due.toDateString() === tomorrow.toDateString()
}

// Check if task is due this week
function isDueThisWeek(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = new Date(dueDate)
    const today = new Date()
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

export default function TasksPage() {
    const [filter, setFilter] = useState<"all" | "my_tasks">("my_tasks")
    const [showCompleted, setShowCompleted] = useState(false)

    // Fetch incomplete tasks
    const { data: incompleteTasks, isLoading: loadingIncomplete } = useTasks({
        my_tasks: filter === "my_tasks",
        is_completed: false,
        per_page: 100,
    })

    // Fetch completed tasks (only when shown)
    const { data: completedTasks, isLoading: loadingCompleted } = useTasks({
        my_tasks: filter === "my_tasks",
        is_completed: true,
        per_page: 50,
    })

    const completeTask = useCompleteTask()
    const uncompleteTask = useUncompleteTask()

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        if (isCompleted) {
            await uncompleteTask.mutateAsync(taskId)
        } else {
            await completeTask.mutateAsync(taskId)
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
            >
                <Checkbox
                    className="mt-0.5"
                    checked={task.is_completed}
                    onCheckedChange={() => handleTaskToggle(task.id, task.is_completed)}
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
                        <Link href={`/cases/${task.case_id}`} className="text-sm text-muted-foreground hover:underline">
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

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Tasks</h1>
                    <Button disabled>
                        <PlusIcon className="mr-2 size-4" />
                        Add Task
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-4 p-6">
                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex gap-2">
                        <Button
                            variant={filter === "my_tasks" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setFilter("my_tasks")}
                        >
                            My Tasks
                        </Button>
                        <Button
                            variant={filter === "all" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setFilter("all")}
                        >
                            All Tasks
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

                {/* Tasks Card */}
                {!isLoading && (
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
            </div>
        </div>
    )
}
