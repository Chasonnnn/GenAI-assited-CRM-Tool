import { Suspense } from "react"

import { SurrogatesPageClient } from "./page.client"

function SurrogatesPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="space-y-2">
                <div className="h-9 w-56 rounded-md bg-muted" />
                <div className="h-4 w-40 rounded-md bg-muted/70" />
            </div>
            <div className="rounded-2xl border border-border bg-card p-6">
                <div className="h-10 w-full rounded-md bg-muted/70" />
            </div>
            <div className="rounded-2xl border border-border bg-card p-6">
                <div className="space-y-3">
                    <div className="h-10 w-full rounded-md bg-muted/70" />
                    <div className="h-10 w-full rounded-md bg-muted/60" />
                    <div className="h-10 w-full rounded-md bg-muted/50" />
                </div>
            </div>
        </div>
    )
}

export default function SurrogatesPage() {
    return (
        <Suspense fallback={<SurrogatesPageSkeleton />}>
            <SurrogatesPageClient />
        </Suspense>
    )
}
