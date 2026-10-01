"use client"

import { useState } from "react"
import type * as React from "react"
import { AlertCircleIcon, ArrowLeftIcon, Loader2Icon, PlusIcon, RocketIcon, SlidersHorizontalIcon } from "lucide-react"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useMediaQuery } from "@/hooks/use-media-query"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import { WORKFLOW_SUBJECT_LABELS } from "@/lib/workflows/workflow-editor-state"
import { WorkflowActionPanel } from "./workflow-action-panel"
import { WorkflowBuildPanel } from "./workflow-build-panel"
import { WorkflowCanvas } from "./workflow-canvas"
import { WorkflowConditionsPanel } from "./workflow-conditions-panel"
import { WorkflowTriggerPanel } from "./workflow-trigger-panel"

// Side panels stack into sheets below the lg breakpoint, where three columns no longer fit.
const COMPACT_LAYOUT_QUERY = "(max-width: 1023px)"

function WorkflowInspector({ controller }: { controller: WorkflowEditorController }) {
    const { selection, selectedActionIndex, state } = controller
    if (selection.kind === "conditions") return <WorkflowConditionsPanel controller={controller} />
    if (selection.kind === "action") {
        const action = state.actions[selectedActionIndex]
        if (action) return <WorkflowActionPanel controller={controller} action={action} index={selectedActionIndex} />
    }
    return <WorkflowTriggerPanel controller={controller} />
}

/** Save button that stays focusable while disabled so the blocking reason shows in a tooltip. */
function SaveButton({
    reason,
    disabled,
    children,
    ...props
}: React.ComponentProps<typeof Button> & { reason: string | null }) {
    if (!reason) {
        return (
            <Button size="sm" disabled={disabled} {...props}>
                {children}
            </Button>
        )
    }
    return (
        <Tooltip>
            <TooltipTrigger
                render={
                    <Button
                        size="sm"
                        disabled
                        focusableWhenDisabled
                        className="data-disabled:cursor-not-allowed data-disabled:opacity-50"
                        {...props}
                    />
                }
            >
                {children}
            </TooltipTrigger>
            <TooltipContent>{reason}</TooltipContent>
        </Tooltip>
    )
}

function WorkflowEditorHeader({ controller }: { controller: WorkflowEditorController }) {
    const { state, handlers, isEditing, editingWorkflow, listHref } = controller
    const { workflowName, workflowScope, savedSubjectType, isSaving, hasServerErrors, workflowValidationError } = state
    const saveDisabled = isSaving || hasServerErrors || Boolean(workflowValidationError)
    const statusLabel = !isEditing ? "Draft" : editingWorkflow?.is_enabled ? "Enabled" : "Disabled"

    return (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/95 px-4 py-2.5 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6 lg:h-14 lg:flex-nowrap lg:py-0">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2.5 sm:gap-3">
                <Button variant="ghost" size="icon" aria-label="Back to workflows" render={<Link href={listHref} />}>
                    <ArrowLeftIcon className="size-5" />
                </Button>
                <Input
                    aria-label="Workflow name"
                    value={workflowName}
                    onChange={(event) => handlers.setWorkflowName(event.target.value)}
                    placeholder="New workflow"
                    className="h-8 min-w-0 flex-1 border-none bg-transparent px-0 text-base font-medium focus-visible:ring-0 sm:max-w-xs lg:w-72 lg:flex-none"
                />
                <Badge
                    variant={statusLabel === "Enabled" ? "default" : "secondary"}
                    className="h-5 rounded-full px-2 text-[11px]"
                >
                    {statusLabel}
                </Badge>
                <Badge variant="outline" className="h-5 rounded-full px-2 text-[11px]">
                    {workflowScope === "org" ? "Organization" : "Personal"}
                </Badge>
                <Badge variant="outline" className="h-5 rounded-full px-2 text-[11px]">
                    {WORKFLOW_SUBJECT_LABELS[savedSubjectType]}
                </Badge>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
                {isEditing ? (
                    <SaveButton
                        reason={workflowValidationError}
                        onClick={() => handlers.saveWorkflow({ isEnabled: true })}
                        disabled={saveDisabled}
                    >
                        {isSaving ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : null}
                        Save changes
                    </SaveButton>
                ) : (
                    <>
                        <SaveButton
                            reason={workflowValidationError}
                            variant="secondary"
                            onClick={() => handlers.saveWorkflow({ isEnabled: false })}
                            disabled={saveDisabled}
                        >
                            Save draft
                        </SaveButton>
                        <SaveButton
                            reason={workflowValidationError}
                            onClick={() => handlers.saveWorkflow({ isEnabled: true })}
                            disabled={saveDisabled}
                        >
                            {isSaving ? (
                                <Loader2Icon className="animate-spin" aria-hidden="true" />
                            ) : (
                                <RocketIcon aria-hidden="true" />
                            )}
                            Launch workflow
                        </SaveButton>
                    </>
                )}
            </div>
        </div>
    )
}

function WorkflowEditorAlerts({ controller }: { controller: WorkflowEditorController }) {
    const { serverErrors, validationError } = controller.state
    if (serverErrors.length === 0 && !validationError) return null
    return (
        <div className="space-y-2 px-4 pt-4 sm:px-6">
            {serverErrors.length > 0 ? (
                <div
                    role="alert"
                    className="flex items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm"
                >
                    <AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                    {serverErrors.length === 1 ? (
                        <p className="text-destructive">{serverErrors[0]}</p>
                    ) : (
                        <div className="space-y-2">
                            <p className="font-medium text-destructive">Fix these errors</p>
                            <ul className="space-y-1 text-xs text-destructive">
                                {serverErrors.map((message) => (
                                    <li key={message}>• {message}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            ) : null}
            {validationError ? (
                <div
                    role="alert"
                    className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm"
                >
                    <AlertCircleIcon className="size-4 shrink-0 text-destructive" aria-hidden="true" />
                    <span>{validationError}</span>
                </div>
            ) : null}
        </div>
    )
}

export function WorkflowEditorScreen({ controller }: { controller: WorkflowEditorController }) {
    const isCompact = useMediaQuery(COMPACT_LAYOUT_QUERY)
    const [compactPanel, setCompactPanel] = useState<"inspector" | "build" | null>(null)
    const { setSelection, handlers } = controller

    const selectNode = (selection: WorkflowEditorSelection) => {
        setSelection(selection)
        if (isCompact) setCompactPanel("inspector")
    }
    const addActionFromPalette = (actionType: string) => {
        handlers.addAction(actionType)
        if (isCompact) setCompactPanel("inspector")
    }
    const requestAddAction = () => {
        if (isCompact) {
            setCompactPanel("build")
            return
        }
        handlers.addAction()
    }

    return (
        <div className="flex h-[calc(100dvh-4rem)] min-h-0 flex-col bg-background">
            <WorkflowEditorHeader controller={controller} />
            <WorkflowEditorAlerts controller={controller} />
            {isCompact ? (
                <>
                    <div className="flex items-center justify-between gap-2 px-4 pt-4 sm:px-6">
                        <Button variant="outline" size="sm" onClick={() => setCompactPanel("inspector")}>
                            <SlidersHorizontalIcon aria-hidden="true" />
                            Configure
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setCompactPanel("build")}>
                            <PlusIcon aria-hidden="true" />
                            Add action
                        </Button>
                    </div>
                    <div className="flex min-h-0 flex-1 flex-col p-4 sm:p-6">
                        <WorkflowCanvas controller={controller} onSelect={selectNode} onRequestAddAction={requestAddAction} />
                    </div>
                    <Sheet open={compactPanel === "inspector"} onOpenChange={(open) => !open && setCompactPanel(null)}>
                        <SheetContent side="left" className="w-[min(100vw-2rem,22rem)] p-0 [&>div]:h-full">
                            <SheetHeader className="sr-only">
                                <SheetTitle>Configure step</SheetTitle>
                            </SheetHeader>
                            <div className="flex h-full flex-col p-3 pt-12">
                                <WorkflowInspector controller={controller} />
                            </div>
                        </SheetContent>
                    </Sheet>
                    <Sheet open={compactPanel === "build"} onOpenChange={(open) => !open && setCompactPanel(null)}>
                        <SheetContent side="right" className="w-[min(100vw-2rem,20rem)] p-0">
                            <SheetHeader className="sr-only">
                                <SheetTitle>Add action</SheetTitle>
                            </SheetHeader>
                            <div className="flex h-full flex-col p-3 pt-12">
                                <WorkflowBuildPanel controller={controller} onAddAction={addActionFromPalette} />
                            </div>
                        </SheetContent>
                    </Sheet>
                </>
            ) : (
                <div className="grid min-h-0 flex-1 grid-cols-[18rem_minmax(0,1fr)_16rem] gap-4 p-6">
                    <WorkflowInspector controller={controller} />
                    <WorkflowCanvas controller={controller} onSelect={selectNode} onRequestAddAction={requestAddAction} />
                    <WorkflowBuildPanel controller={controller} onAddAction={addActionFromPalette} />
                </div>
            )}
        </div>
    )
}
