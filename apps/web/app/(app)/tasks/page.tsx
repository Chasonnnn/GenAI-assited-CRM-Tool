import { Suspense } from "react"

import TasksPageClient from "./page.client"

function TasksPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="space-y-2">
                <div className="h-9 w-44 rounded-md bg-muted" />
                <div className="h-4 w-72 rounded-md bg-muted/70" />
            </div>
            <div className="rounded-lg border bg-card p-4">
                <div className="h-10 w-full rounded-md bg-muted/70" />
            </div>
            <div className="rounded-lg border bg-card p-4">
                <div className="space-y-3">
                    <div className="h-12 w-full rounded-md bg-muted/70" />
                    <div className="h-12 w-full rounded-md bg-muted/60" />
                    <div className="h-12 w-full rounded-md bg-muted/50" />
                </div>
            </div>
        </div>
    )
}

export default function TasksPage() {
    return (
        <Suspense fallback={<TasksPageSkeleton />}>
            <TasksPageClient />
        </Suspense>
    )
}
