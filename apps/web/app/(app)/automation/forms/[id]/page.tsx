import { notFound } from "next/navigation"

import FormBuilderPageClient from "./page.client"
import { parseWorkspaceTab } from "@/lib/forms/form-builder-workspace-tab"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
    searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function FormBuilderPage({ params, searchParams }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const formId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!formId) {
        notFound()
    }
    const rawTab = (await searchParams).tab
    const initialTab = parseWorkspaceTab(Array.isArray(rawTab) ? rawTab[0] : rawTab)
    if (formId === "new") {
        return <FormBuilderPageClient initialTab={initialTab} />
    }

    const status = await getServerRouteResourceStatus(
        `/forms/${encodeURIComponent(formId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <FormBuilderPageClient initialTab={initialTab} />
}
