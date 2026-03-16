import { notFound } from "next/navigation"

import PlatformEmailTemplatePageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function PlatformEmailTemplatePage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const templateId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!templateId) {
        notFound()
    }
    if (templateId === "new") {
        return <PlatformEmailTemplatePageClient />
    }

    const status = await getServerRouteResourceStatus(
        `/platform/templates/email/${encodeURIComponent(templateId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <PlatformEmailTemplatePageClient />
}
