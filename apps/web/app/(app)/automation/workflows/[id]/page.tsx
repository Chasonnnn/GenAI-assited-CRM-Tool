import { notFound } from "next/navigation"

import WorkflowEditorPageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"
import { getWorkflowEditorPreset } from "@/lib/workflows/workflow-editor-state"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
    searchParams: Promise<Record<string, string | string[] | undefined>>
}

function firstSearchParam(value: string | string[] | undefined): string | undefined {
    return Array.isArray(value) ? value[0] : value
}

export default async function WorkflowEditorPage({ params, searchParams }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const workflowId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!workflowId) {
        notFound()
    }

    const resolvedSearchParams = await searchParams
    const scopeParam = firstSearchParam(resolvedSearchParams.scope)
    const initialScope = scopeParam === "org" ? "org" : "personal"

    if (workflowId === "new") {
        return (
            <WorkflowEditorPageClient
                workflowId={null}
                initialScope={initialScope}
                initialPreset={getWorkflowEditorPreset(resolvedSearchParams)}
            />
        )
    }

    const status = await getServerRouteResourceStatus(`/workflows/${encodeURIComponent(workflowId)}`)
    if (status === "not_found") {
        notFound()
    }

    return <WorkflowEditorPageClient workflowId={workflowId} initialScope={initialScope} />
}
