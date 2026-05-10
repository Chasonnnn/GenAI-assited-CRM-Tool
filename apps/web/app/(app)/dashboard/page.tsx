import { Suspense } from "react"

import DashboardPageClient from "./page.client"

function DashboardPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="space-y-2">
                <div className="h-9 w-52 rounded-md bg-muted" />
                <div className="h-4 w-80 rounded-md bg-muted/70" />
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="h-32 rounded-lg border bg-card p-4" />
                <div className="h-32 rounded-lg border bg-card p-4" />
                <div className="h-32 rounded-lg border bg-card p-4" />
                <div className="h-32 rounded-lg border bg-card p-4" />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
                <div className="h-80 rounded-lg border bg-card p-4" />
                <div className="h-80 rounded-lg border bg-card p-4" />
            </div>
        </div>
    )
}

export default function DashboardPage() {
    return (
        <Suspense fallback={<DashboardPageSkeleton />}>
            <DashboardPageClient />
        </Suspense>
    )
}
