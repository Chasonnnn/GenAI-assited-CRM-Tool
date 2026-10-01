"use client"

import type { ReactNode } from "react"
import { GripVerticalIcon, SparklesIcon } from "lucide-react"

import Link from "@/components/app-link"
import { Button } from "@/components/ui/button"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import { cn } from "@/lib/utils"
import { EditorColumn } from "./inspector-section"
import { ACTION_GROUP_ORDER, NodeIcon, getActionMeta } from "./node-meta"

const PALETTE_ROW_CLASS =
    "flex h-8 w-full items-center gap-2 rounded-md border border-border bg-card px-2 text-left text-xs outline-none transition-colors hover:bg-muted/60 focus-visible:ring-[3px] focus-visible:ring-ring/50"

function PaletteGroup({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section className="space-y-1.5">
            <h3 className="flex items-center gap-1.5 px-0.5 text-sm font-semibold">
                <GripVerticalIcon aria-hidden="true" className="size-3.5 text-muted-foreground" />
                {title}
            </h3>
            <ul className="space-y-1">{children}</ul>
        </section>
    )
}

export function WorkflowBuildPanel({
    controller,
    onAddAction,
    className,
}: {
    controller: WorkflowEditorController
    onAddAction: (actionType: string) => void
    className?: string
}) {
    const { options, canUseAI, state } = controller
    const groupRank = (value: string) => ACTION_GROUP_ORDER.indexOf(getActionMeta(value).group)
    const actionTypes = options.filteredActionTypes.toSorted((a, b) => groupRank(a.value) - groupRank(b.value))

    return (
        // Bottom padding keeps the last item clear of the global floating AI button.
        <EditorColumn
            aria-label="Build"
            data-testid="workflow-build-panel"
            className={cn("gap-5 rounded-lg border border-border bg-card/60 p-2.5 pb-16", className)}
        >
            {canUseAI ? (
                <PaletteGroup title="Agents">
                    <li>
                        <Link
                            href={`/automation/ai-builder?mode=workflow&scope=${state.workflowScope}`}
                            className={PALETTE_ROW_CLASS}
                        >
                            <NodeIcon icon={SparklesIcon} tone="rose" size="sm" className="size-4 [&_svg]:size-2.5" />
                            <span className="truncate">Generate with AI</span>
                        </Link>
                    </li>
                </PaletteGroup>
            ) : null}
            <PaletteGroup title="Actions">
                {actionTypes.map((actionType) => {
                    const meta = getActionMeta(actionType.value)
                    return (
                        <li key={actionType.value}>
                            <Button
                                unstyled
                                type="button"
                                title={actionType.description || undefined}
                                onClick={() => onAddAction(actionType.value)}
                                className={PALETTE_ROW_CLASS}
                            >
                                <NodeIcon icon={meta.icon} tone={meta.tone} size="sm" className="size-4 [&_svg]:size-2.5" />
                                <span className="truncate">{actionType.label}</span>
                            </Button>
                        </li>
                    )
                })}
                {actionTypes.length === 0 ? (
                    <li className="px-0.5 text-xs text-muted-foreground">No actions for this trigger.</li>
                ) : null}
            </PaletteGroup>
        </EditorColumn>
    )
}
