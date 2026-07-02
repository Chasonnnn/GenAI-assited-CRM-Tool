"use client"

import { CalendarCheckIcon, PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

export function SurrogateTasksEmptyState({ onAddTask }: { onAddTask: () => void }) {
    return (
        <Card className="flex flex-col items-center justify-center py-16 text-center">
            <div className="rounded-full bg-muted/50 p-4 mb-4">
                <CalendarCheckIcon className="size-8 text-muted-foreground/60" />
            </div>
            <p className="text-sm font-medium text-muted-foreground mb-1">
                No tasks yet
            </p>
            <p className="text-xs text-muted-foreground/70 mb-4">
                Create a task to track work for this surrogate
            </p>
            <Button size="sm" variant="outline" onClick={onAddTask}>
                <PlusIcon className="size-4 mr-1.5" />
                Add First Task
            </Button>
        </Card>
    )
}
