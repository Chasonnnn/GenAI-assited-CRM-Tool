import type { ReactNode } from "react"
import { ActivityIcon, PlusIcon } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"

export function AutomationPageHeader({
    activeTab,
    onOpenExecutions,
    onCreateTemplate,
    canViewExecutions = true,
    onCreateWorkflow,
}: {
    activeTab: string
    onOpenExecutions: () => void
    onCreateTemplate: () => void
    /** Pass can("manage_automation"): the executions API denies every other role. */
    canViewExecutions?: boolean
    /** Set on the Workflow Templates tab, which has no create action of its own. */
    onCreateWorkflow?: (() => void) | undefined
}) {
    let actions: ReactNode = null
    if (activeTab === "workflows") {
        actions =
            canViewExecutions || onCreateWorkflow ? (
                <>
                    {canViewExecutions ? (
                        <Button variant="outline" onClick={onOpenExecutions}>
                            <ActivityIcon className="mr-2 size-4" />
                            Execution History
                        </Button>
                    ) : null}
                    {onCreateWorkflow ? (
                        <Button onClick={onCreateWorkflow}>
                            <PlusIcon className="mr-2 size-4" />
                            Create Workflow
                        </Button>
                    ) : null}
                </>
            ) : null
    } else if (activeTab === "email-templates") {
        actions = (
            <Button onClick={onCreateTemplate}>
                <PlusIcon className="mr-2 size-4" />
                New Template
            </Button>
        )
    }

    return <PageHeader title="Workflows" actions={actions} />
}
