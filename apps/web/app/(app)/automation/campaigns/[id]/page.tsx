import { notFound } from "next/navigation"
import { Suspense } from "react"

import CampaignDetailPageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function CampaignDetailPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const campaignId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!campaignId) {
        notFound()
    }

    const status = await getServerRouteResourceStatus(
        `/campaigns/${encodeURIComponent(campaignId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return (
        <Suspense fallback={<CampaignDetailPageSkeleton />}>
            <CampaignDetailPageClient />
        </Suspense>
    )
}

function CampaignDetailPageSkeleton() {
    return (
        <div className="space-y-6 p-6">
            <div className="h-8 w-56 rounded-md bg-muted" />
            <div className="grid gap-4 md:grid-cols-3">
                <div className="h-28 rounded-lg border bg-card" />
                <div className="h-28 rounded-lg border bg-card" />
                <div className="h-28 rounded-lg border bg-card" />
            </div>
            <div className="h-96 rounded-lg border bg-card" />
        </div>
    )
}
