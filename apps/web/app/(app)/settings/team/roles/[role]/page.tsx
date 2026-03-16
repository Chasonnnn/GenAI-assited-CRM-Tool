import { notFound } from "next/navigation"

import RoleDetailPageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ role?: string | string[] }>
}

export default async function RoleDetailPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawRole = resolvedParams.role
    const role = Array.isArray(rawRole) ? rawRole[0] : rawRole

    if (!role) {
        notFound()
    }

    const status = await getServerRouteResourceStatus(
        `/settings/permissions/roles/${encodeURIComponent(role)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <RoleDetailPageClient />
}
