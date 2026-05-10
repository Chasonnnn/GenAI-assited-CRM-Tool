import { notFound } from "next/navigation"
import type { Metadata } from "next"

import PlatformWorkflowTemplatePageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

export const metadata: Metadata = {
    title: "Workflow template | SurrogacyForce Ops",
    description: "Review and edit a platform workflow template.",
}

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function PlatformWorkflowTemplatePage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const templateId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!templateId) {
        notFound()
    }
    if (templateId === "new") {
        return <PlatformWorkflowTemplatePageClient />
    }

    const status = await getServerRouteResourceStatus(
        `/platform/templates/workflows/${encodeURIComponent(templateId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <PlatformWorkflowTemplatePageClient />
}
