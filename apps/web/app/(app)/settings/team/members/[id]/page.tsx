import { notFound } from "next/navigation"

import MemberDetailPageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function MemberDetailPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const memberId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!memberId) {
        notFound()
    }

    const status = await getServerRouteResourceStatus(
        `/settings/permissions/members/${encodeURIComponent(memberId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <MemberDetailPageClient />
}
