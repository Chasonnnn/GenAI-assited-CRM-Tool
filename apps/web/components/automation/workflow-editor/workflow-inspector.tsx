"use client"

import { ArrowDownIcon, PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import { cn } from "@/lib/utils"
import { ACTION_GROUP_ORDER, NodeIcon, getActionMeta, getTriggerIcon } from "./node-meta"
import { ActionStepControls, WorkflowActionPanel } from "./workflow-action-panel"
import { WorkflowStepHistory } from "./workflow-step-history"
import { WorkflowTriggerPanel } from "./workflow-trigger-panel"

/** Menu of step types that inserts the chosen one at a position. */
function AddStepMenu({
    controller,
    index,
    onAdded,
}: {
    controller: WorkflowEditorController
    index: number
    onAdded: (index: number) => void
}) {
    const actionTypes = controller.options.filteredActionTypes
    return (
        <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="w-full" />}>
                <PlusIcon aria-hidden="true" />
                Add next step
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="center" className="max-h-80 w-(--anchor-width) min-w-56">
                {ACTION_GROUP_ORDER.map((group) => {
                    const items = actionTypes.filter((actionType) => getActionMeta(actionType.value).group === group)
                    if (items.length === 0) return null
                    return (
                        <DropdownMenuGroup key={group}>
                            <DropdownMenuLabel>{group}</DropdownMenuLabel>
                            {items.map((actionType) => {
                                const meta = getActionMeta(actionType.value)
                                return (
                                    <DropdownMenuItem
                                        key={actionType.value}
                                        onClick={() => {
                                            controller.handlers.addAction(actionType.value, index)
                                            onAdded(index)
                                        }}
                                    >
                                        <NodeIcon icon={meta.icon} tone={meta.tone} size="sm" />
                                        {actionType.label}
                                    </DropdownMenuItem>
                                )
                            })}
                        </DropdownMenuGroup>
                    )
                })}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

/**
 * Settings for the selected step: its fields, its past runs on saved workflows, and a footer that
 * walks to the next step or adds one.
 */
export function WorkflowInspector({
    controller,
    onSelect,
    onClose,
    onRevealStep,
    className,
}: {
    controller: WorkflowEditorController
    onSelect: (selection: WorkflowEditorSelection) => void
    onClose?: () => void
    /** Scrolls the canvas to a step after the footer moves to or adds it. */
    onRevealStep: (index: number) => void
    className?: string
}) {
    const { selection, selectedActionIndex, state, options, workflowId } = controller
    const action = selection.kind === "action" ? state.actions[selectedActionIndex] : undefined
    if (selection.kind === "none" || (selection.kind === "action" && !action)) return null

    const isTrigger = selection.kind === "trigger"
    const actionIndex = isTrigger ? -1 : selectedActionIndex
    const nextAction = state.actions[actionIndex + 1]
    const meta = action ? getActionMeta(action.action_type) : null
    const Icon = meta?.icon ?? getTriggerIcon(state.triggerType)
    const title = isTrigger
        ? "Trigger"
        : options.actionTypeOptions.find((option) => option.value === action?.action_type)?.label ?? `Step ${actionIndex + 1}`

    const settings = action ? (
        <WorkflowActionPanel controller={controller} action={action} index={actionIndex} />
    ) : (
        <WorkflowTriggerPanel controller={controller} />
    )

    return (
        <section aria-label="Step settings" className={cn("flex min-h-0 flex-col", className)}>
            <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border pr-1.5 pl-3">
                <NodeIcon icon={Icon} tone={meta?.tone ?? "violet"} size="sm" />
                <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</h2>
                {action ? <ActionStepControls controller={controller} index={actionIndex} /> : null}
                {onClose ? (
                    <Button size="icon-sm" variant="ghost" className="size-7" aria-label="Close step settings" onClick={onClose}>
                        <XIcon aria-hidden="true" />
                    </Button>
                ) : null}
            </header>

            {/* Keyed by step so switching steps resets to Settings. */}
            <Tabs key={isTrigger ? "trigger" : action?.clientId} defaultValue="settings" className="flex min-h-0 flex-1 flex-col gap-0">
                <TabsList className="mx-3 mt-2.5 shrink-0">
                    <TabsTrigger value="settings">Settings</TabsTrigger>
                    {workflowId ? <TabsTrigger value="history">History</TabsTrigger> : null}
                </TabsList>
                <TabsContent value="settings" className="flex min-h-0 flex-1 flex-col p-2.5">
                    {settings}
                </TabsContent>
                {workflowId ? (
                    <TabsContent value="history" className="min-h-0 flex-1 overflow-y-auto px-2.5 py-1">
                        <WorkflowStepHistory
                            workflowId={workflowId}
                            {...(action ? { step: { index: actionIndex, actionType: action.action_type } } : {})}
                        />
                    </TabsContent>
                ) : null}
            </Tabs>

            <footer className="shrink-0 border-t border-border p-2.5">
                {nextAction ? (
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        onClick={() => {
                            onSelect({ kind: "action", clientId: nextAction.clientId })
                            onRevealStep(actionIndex + 1)
                        }}
                    >
                        <ArrowDownIcon aria-hidden="true" />
                        Next step
                    </Button>
                ) : (
                    <AddStepMenu controller={controller} index={actionIndex + 1} onAdded={onRevealStep} />
                )}
            </footer>
        </section>
    )
}
