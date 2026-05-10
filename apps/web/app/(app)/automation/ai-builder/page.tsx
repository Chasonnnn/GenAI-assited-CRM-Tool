import { Suspense } from "react"

import AIWorkflowBuilderPageClient from "./page.client"

function AIWorkflowBuilderPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="space-y-2">
                <div className="h-9 w-72 rounded-md bg-muted" />
                <div className="h-4 w-96 max-w-full rounded-md bg-muted/70" />
            </div>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="h-[520px] rounded-lg border bg-card p-4" />
                <div className="h-[520px] rounded-lg border bg-card p-4" />
            </div>
        </div>
    )
}

export default function AIWorkflowBuilderPage() {
    return (
        <Suspense fallback={<AIWorkflowBuilderPageSkeleton />}>
            <AIWorkflowBuilderPageClient />
        </Suspense>
    )
}
