import { Suspense } from "react"

import DonorsPageClient from "./page.client"

function DonorsPageSkeleton() {
    return (
        <div className="space-y-6 p-6" role="status" aria-label="Loading donors">
            <div className="h-9 w-40 rounded-md bg-muted" />
            <div className="h-10 w-64 rounded-md bg-muted/70" />
            <div className="h-14 w-full rounded-md bg-muted/70" />
            <div className="h-96 w-full rounded-lg border bg-card" />
        </div>
    )
}

export default function DonorsPage() {
    return (
        <Suspense fallback={<DonorsPageSkeleton />}>
            <DonorsPageClient />
        </Suspense>
    )
}
