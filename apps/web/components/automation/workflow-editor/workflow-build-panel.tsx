"use client"

import type { PointerEvent as ReactPointerEvent, ReactNode } from "react"
import { ChevronUpIcon, GripVerticalIcon, SparklesIcon } from "lucide-react"

import Link from "@/components/app-link"
import { Button } from "@/components/ui/button"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import { cn } from "@/lib/utils"
import { ACTION_GROUP_ORDER, NodeIcon, getActionMeta, type ActionGroup } from "./node-meta"

const PALETTE_ROW_CLASS =
    "group/row flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-xs outline-none transition-colors hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"

function PaletteGroup({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section className="space-y-0.5">
            <h3 className="px-2 pb-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">{title}</h3>
            <ul className="space-y-0.5">{children}</ul>
        </section>
    )
}

/**
 * Step palette. Clicking a step adds it after the selected one; dragging it onto the canvas
 * drops it into the slot under the pointer.
 */
export function WorkflowBuildPanel({
    controller,
    onAddAction,
    onItemPointerDown,
    collapsed = false,
    onToggleCollapsed,
    className,
}: {
    controller: WorkflowEditorController
    onAddAction: (actionType: string) => void
    onItemPointerDown?: (actionType: string, label: string, event: ReactPointerEvent) => void
    collapsed?: boolean
    /** Omitted where the panel cannot collapse, such as inside a sheet. */
    onToggleCollapsed?: () => void
    className?: string
}) {
    const { options, canUseAI, state } = controller
    const groups = ACTION_GROUP_ORDER.map((group) => ({
        group,
        items: options.filteredActionTypes.filter((actionType) => getActionMeta(actionType.value).group === group),
    })).filter((entry): entry is { group: ActionGroup; items: typeof options.filteredActionTypes } => entry.items.length > 0)

    return (
        <aside
            aria-label="Build"
            data-testid="workflow-build-panel"
            className={cn("flex min-h-0 flex-col text-xs", className)}
        >
            {onToggleCollapsed ? (
                <div className="flex h-10 shrink-0 items-center justify-between gap-2 pr-1.5 pl-3">
                    <h2 className="text-sm font-semibold">Steps</h2>
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        className="size-7"
                        aria-expanded={!collapsed}
                        aria-controls="workflow-build-panel-body"
                        aria-label={collapsed ? "Expand steps" : "Collapse steps"}
                        onClick={onToggleCollapsed}
                    >
                        <ChevronUpIcon
                            aria-hidden="true"
                            className={cn("transition-transform duration-200", collapsed && "rotate-180")}
                        />
                    </Button>
                </div>
            ) : null}
            <div
                id="workflow-build-panel-body"
                hidden={collapsed}
                className={cn("min-h-0 space-y-4 overflow-y-auto p-1.5 pb-3", onToggleCollapsed && "border-t border-border")}
            >
                {canUseAI ? (
                    <PaletteGroup title="Agents">
                        <li>
                            <Link
                                href={`/automation/ai-builder?mode=workflow&scope=${state.workflowScope}`}
                                className={PALETTE_ROW_CLASS}
                            >
                                <NodeIcon icon={SparklesIcon} tone="rose" size="sm" />
                                <span className="truncate">Generate with AI</span>
                            </Link>
                        </li>
                    </PaletteGroup>
                ) : null}
                {groups.map(({ group, items }) => (
                    <PaletteGroup key={group} title={group}>
                        {items.map((actionType) => {
                            const meta = getActionMeta(actionType.value)
                            return (
                                <li key={actionType.value}>
                                    <Button
                                        unstyled
                                        type="button"
                                        title={actionType.description || undefined}
                                        onClick={() => onAddAction(actionType.value)}
                                        onPointerDown={
                                            onItemPointerDown
                                                ? (event) => onItemPointerDown(actionType.value, actionType.label, event)
                                                : undefined
                                        }
                                        className={cn(PALETTE_ROW_CLASS, onItemPointerDown && "cursor-grab")}
                                    >
                                        <NodeIcon icon={meta.icon} tone={meta.tone} size="sm" />
                                        <span className="min-w-0 flex-1 truncate">{actionType.label}</span>
                                        {onItemPointerDown ? (
                                            <GripVerticalIcon
                                                aria-hidden="true"
                                                className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover/row:opacity-100"
                                            />
                                        ) : null}
                                    </Button>
                                </li>
                            )
                        })}
                    </PaletteGroup>
                ))}
                {groups.length === 0 ? (
                    <p className="px-2 text-xs text-muted-foreground">No actions for this trigger.</p>
                ) : null}
            </div>
        </aside>
    )
}
