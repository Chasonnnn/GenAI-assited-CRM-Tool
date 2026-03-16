import { notFound } from "next/navigation"

import PlatformFormTemplatePageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function PlatformFormTemplatePage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const templateId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!templateId) {
        notFound()
    }
    if (templateId === "new") {
        return <PlatformFormTemplatePageClient />
    }

    const status = await getServerRouteResourceStatus(
        `/platform/templates/forms/${encodeURIComponent(templateId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <PlatformFormTemplatePageClient />
}
