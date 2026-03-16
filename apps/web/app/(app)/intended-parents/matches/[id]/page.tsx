import { notFound } from "next/navigation"

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

    return <MatchDetailPageClient />
}
