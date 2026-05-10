import { Suspense } from "react"

import MatchesPageClient from "./page.client"

function MatchesPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="space-y-2">
                <div className="h-9 w-56 rounded-md bg-muted" />
                <div className="h-4 w-80 rounded-md bg-muted/70" />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
                <div className="h-28 rounded-lg border bg-card" />
                <div className="h-28 rounded-lg border bg-card" />
                <div className="h-28 rounded-lg border bg-card" />
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
