import { Suspense } from "react"

import MetaIntegrationPageClient from "./page.client"

function MetaIntegrationPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="space-y-2">
                <div className="h-9 w-56 rounded-md bg-muted" />
                <div className="h-4 w-96 max-w-full rounded-md bg-muted/70" />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
                <div className="h-64 rounded-lg border bg-card p-4" />
                <div className="h-64 rounded-lg border bg-card p-4" />
            </div>
        </div>
    )
}

export default function MetaIntegrationPage() {
    return (
        <Suspense fallback={<MetaIntegrationPageSkeleton />}>
            <MetaIntegrationPageClient />
        </Suspense>
    )
}
