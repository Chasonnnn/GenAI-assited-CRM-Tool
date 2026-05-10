import { notFound } from "next/navigation"
import { Suspense } from "react"

import MatchDetailPageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function MatchDetailPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const matchId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!matchId) {
        notFound()
    }

    const status = await getServerRouteResourceStatus(
        `/matches/${encodeURIComponent(matchId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return (
        <Suspense fallback={<MatchDetailPageSkeleton />}>
            <MatchDetailPageClient />
        </Suspense>
    )
}

function MatchDetailPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="h-8 w-64 rounded-md bg-muted" />
            <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
                <div className="h-[28rem] rounded-lg border bg-card" />
                <div className="h-[28rem] rounded-lg border bg-card" />
            </div>
        </div>
    )
}
