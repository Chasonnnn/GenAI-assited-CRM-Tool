"use client"

import { CalendarIcon, ListIcon, PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

import type { SurrogateTasksViewMode } from "./use-surrogate-task-view-mode"

interface SurrogateTasksCalendarHeaderProps {
    taskCount: number
    viewMode: SurrogateTasksViewMode
    onViewModeChange: (mode: SurrogateTasksViewMode) => void
    onAddTask: () => void
}

export function SurrogateTasksCalendarHeader({
    taskCount,
    viewMode,
    onViewModeChange,
    onAddTask,
}: SurrogateTasksCalendarHeaderProps) {
    return (
        <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold tracking-tight">Tasks</h3>
                {taskCount > 0 && (
                    <span className="text-sm font-normal text-muted-foreground">
                        ({taskCount})
                    </span>
                )}
            </div>

            <div className="flex items-center gap-2">
                <div className="flex gap-1 border rounded-lg p-1 bg-background">
                    <Button
                        variant={viewMode === "list" ? "secondary" : "ghost"}
                        size="sm"
                        onClick={() => onViewModeChange("list")}
                    >
                        <ListIcon className="size-4 mr-1" />
                        List
                    </Button>
                    <Button
                        variant={viewMode === "calendar" ? "secondary" : "ghost"}
                        size="sm"
                        onClick={() => onViewModeChange("calendar")}
                    >
                        <CalendarIcon className="size-4 mr-1" />
                        Calendar
                    </Button>
                </div>
                <Button size="sm" onClick={onAddTask}>
                    <PlusIcon className="size-4 mr-1.5" />
                    Add Task
                </Button>
            </div>
        </div>
    )
}
