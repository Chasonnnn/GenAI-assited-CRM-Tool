import { Suspense } from "react"

import MatchesPageClient from "./page.client"

function MatchesPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="h-9 w-56 rounded-md bg-muted" />
            <div className="flex flex-wrap gap-3">
                <div className="h-9 w-[180px] rounded-md bg-muted/70" />
                <div className="h-9 w-36 rounded-md bg-muted/70" />
                <div className="h-9 w-32 rounded-md bg-muted/70" />
            </div>
            <div className="rounded-lg border bg-card p-4">
                <div className="space-y-3">
                    <div className="h-10 w-full rounded-md bg-muted/70" />
                    <div className="h-12 w-full rounded-md bg-muted/60" />
                    <div className="h-12 w-full rounded-md bg-muted/50" />
                </div>
            </div>
        </div>
    )
}

export default function MatchesPage() {
    return (
        <Suspense fallback={<MatchesPageSkeleton />}>
            <MatchesPageClient />
        </Suspense>
    )
}
