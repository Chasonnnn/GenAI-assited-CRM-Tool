"use client"

import { GripVerticalIcon, SparklesIcon } from "lucide-react"

import Link from "@/components/app-link"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import { InspectorPanel, InspectorSection } from "./inspector-section"
import { ACTION_GROUP_ORDER, NodeIcon, getActionMeta, type ActionGroup } from "./node-meta"

export function WorkflowBuildPanel({
    controller,
    onAddAction,
}: {
    controller: WorkflowEditorController
    onAddAction: (actionType: string) => void
}) {
    const { options, canUseAI, state } = controller
    const grouped = new Map<ActionGroup, typeof options.filteredActionTypes>()
    for (const actionType of options.filteredActionTypes) {
        const group = getActionMeta(actionType.value).group
        const bucket = grouped.get(group) ?? []
        bucket.push(actionType)
        grouped.set(group, bucket)
    }

    return (
        <InspectorPanel
            title="Build"
            icon={<GripVerticalIcon aria-hidden="true" className="size-4 text-muted-foreground" />}
            data-testid="workflow-build-panel"
            // Bottom padding keeps the last item clear of the global floating AI button.
            className="[&>div:last-child]:pb-16"
        >
            {canUseAI ? (
                <InspectorSection title="Agents">
                    <Link
                        href={`/automation/ai-builder?mode=workflow&scope=${state.workflowScope}`}
                        className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                    >
                        <NodeIcon icon={SparklesIcon} tone="rose" size="sm" />
                        Generate with AI
                    </Link>
                </InspectorSection>
            ) : null}
            {ACTION_GROUP_ORDER.map((group) => {
                const items = grouped.get(group)
                if (!items || items.length === 0) return null
                return (
                    <InspectorSection key={group} title={group}>
                        <ul className="-mx-2 space-y-0.5">
                            {items.map((actionType) => {
                                const meta = getActionMeta(actionType.value)
                                return (
                                    <li key={actionType.value}>
                                        <button
                                            type="button"
                                            title={actionType.description || undefined}
                                            onClick={() => onAddAction(actionType.value)}
                                            className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50"
                                        >
                                            <NodeIcon icon={meta.icon} tone={meta.tone} size="sm" />
                                            <span className="truncate">{actionType.label}</span>
                                        </button>
                                    </li>
                                )
                            })}
                        </ul>
                    </InspectorSection>
                )
            })}
            {options.filteredActionTypes.length === 0 ? (
                <p className="px-4 py-3 text-sm text-muted-foreground">No actions available for this trigger.</p>
            ) : null}
        </InspectorPanel>
    )
}
