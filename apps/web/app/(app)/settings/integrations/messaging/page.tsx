import { Suspense } from "react"

import MessagingIntegrationPageClient from "./page.client"

function MessagingIntegrationPageSkeleton() {
    return (
        <div className="space-y-6 p-6" aria-label="Loading messaging settings">
            <div className="space-y-2">
                <div className="h-9 w-64 rounded-md bg-muted" />
                <div className="h-4 w-full max-w-xl rounded-md bg-muted/70" />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
                <div className="h-64 rounded-xl border bg-card" />
                <div className="h-64 rounded-xl border bg-card" />
            </div>
            <div className="h-96 rounded-xl border bg-card" />
        </div>
    )
}

export default function MessagingIntegrationPage() {
    return (
        <Suspense fallback={<MessagingIntegrationPageSkeleton />}>
            <MessagingIntegrationPageClient />
        </Suspense>
    )
}
