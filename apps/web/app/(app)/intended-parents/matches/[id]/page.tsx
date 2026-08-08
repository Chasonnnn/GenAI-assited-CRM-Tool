import { notFound } from "next/navigation"
import { Suspense } from "react"
import { dehydrate, HydrationBoundary } from "@tanstack/react-query"

import MatchDetailPageClient from "./page.client"
import type { MatchRead } from "@/lib/api/matches"
import { matchDetailQueryOptions } from "@/lib/queries/matches"
import { createServerQueryClient } from "@/lib/server-query-client"
import {
    fetchServerRouteResource,
    ServerRouteResourceError,
} from "@/lib/server-route-resource"

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

    const resourcePath = `/matches/${encodeURIComponent(matchId)}`
    const queryClient = createServerQueryClient()

    try {
        await queryClient.fetchQuery(
            matchDetailQueryOptions(matchId, () =>
                fetchServerRouteResource<MatchRead>(resourcePath),
            ),
        )
    } catch (error) {
        if (error instanceof ServerRouteResourceError && error.status === 404) {
            notFound()
        }
        if (
            !(error instanceof ServerRouteResourceError) ||
            ![401, 403].includes(error.status)
        ) {
            throw error
        }
    }

    return (
        <HydrationBoundary state={dehydrate(queryClient)}>
            <Suspense fallback={<MatchDetailPageSkeleton />}>
                <MatchDetailPageClient />
            </Suspense>
        </HydrationBoundary>
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
