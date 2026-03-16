import { notFound } from "next/navigation"

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

    return <CampaignDetailPageClient />
}
