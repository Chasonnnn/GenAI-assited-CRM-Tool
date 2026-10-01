"use client"

import { Loader2Icon } from "lucide-react"

import { WorkflowEditorScreen } from "@/components/automation/workflow-editor/workflow-editor-screen"
import { LoadErrorState, NotFoundState, PermissionDeniedState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import type { WorkflowScope } from "@/lib/api/workflows"
import { useWorkflowEditor } from "@/lib/workflows/use-workflow-editor"

type WorkflowEditorPageClientProps = {
    workflowId: string | null
    initialScope: WorkflowScope
}

export default function WorkflowEditorPageClient({ workflowId, initialScope }: WorkflowEditorPageClientProps) {
    const controller = useWorkflowEditor({ workflowId, initialScope })
    const { access, listHref } = controller

    if (access.status === "ok") {
        return <WorkflowEditorScreen controller={controller} />
    }

    if (access.status === "loading") {
        return (
            <div className="flex h-[calc(100dvh-4rem)] items-center justify-center bg-background" role="status">
                <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2Icon className="size-5 animate-spin" aria-hidden="true" />
                    <span>Loading workflow…</span>
                </div>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <PageHeader title="Workflows" back={{ href: listHref, label: "Back to workflows" }} />
            {access.status === "error" ? (
                <LoadErrorState
                    title="Couldn't load workflow"
                    onRetry={access.retry}
                    isRetrying={access.isRetrying}
                    headingLevel={2}
                />
            ) : access.status === "not_found" ? (
                <NotFoundState title="Workflow not found" backHref={listHref} backLabel="Back to workflows" headingLevel={2} />
            ) : (
                <PermissionDeniedState
                    title="No access to this workflow"
                    description="Ask an admin to update your role."
                    secondaryHref={listHref}
                    secondaryLabel="Back to workflows"
                    headingLevel={2}
                />
            )}
        </div>
    )
}
