"use client"

import { useState } from "react"
import type * as React from "react"
import { useRouter } from "next/navigation"
import {
    AlertCircleIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    FolderIcon,
    Loader2Icon,
    PlusIcon,
    SaveIcon,
    SendIcon,
    SlidersHorizontalIcon,
    WorkflowIcon,
} from "lucide-react"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useMediaQuery } from "@/hooks/use-media-query"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import { WorkflowActionPanel } from "./workflow-action-panel"
import { WorkflowBuildPanel } from "./workflow-build-panel"
import { WorkflowCanvas } from "./workflow-canvas"
import { WorkflowTriggerPanel } from "./workflow-trigger-panel"

// Side panels stack into sheets below the lg breakpoint, where three columns no longer fit.
const COMPACT_LAYOUT_QUERY = "(max-width: 1023px)"

function WorkflowInspector({ controller }: { controller: WorkflowEditorController }) {
    const { selection, selectedActionIndex, state } = controller
    if (selection.kind === "action") {
        const action = state.actions[selectedActionIndex]
        if (action) return <WorkflowActionPanel controller={controller} action={action} index={selectedActionIndex} />
    }
    return <WorkflowTriggerPanel controller={controller} />
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const

/** "Jan 28, 2026 09:00AM", the reference's header timestamp format, in local time. */
function formatEditorTimestamp(date: Date): string {
    const hours = date.getHours()
    const hour12 = String(hours % 12 === 0 ? 12 : hours % 12).padStart(2, "0")
    const minutes = String(date.getMinutes()).padStart(2, "0")
    return `${MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()} ${hour12}:${minutes}${hours < 12 ? "AM" : "PM"}`
}

function WorkflowBreadcrumb({ controller }: { controller: WorkflowEditorController }) {
    const router = useRouter()
    const { isEditing, listHref, state } = controller
    return (
        <nav aria-label="Breadcrumb" className="flex h-9 items-center gap-1 text-xs text-muted-foreground">
            <Button variant="ghost" size="icon-sm" className="size-6" aria-label="Go back" onClick={() => router.back()}>
                <ChevronLeftIcon aria-hidden="true" className="size-3.5" />
            </Button>
            <Button variant="ghost" size="icon-sm" className="size-6" aria-label="Go forward" onClick={() => router.forward()}>
                <ChevronRightIcon aria-hidden="true" className="size-3.5" />
            </Button>
            <span aria-hidden="true" className="mx-1.5 h-3.5 w-px bg-border" />
            <ol className="flex min-w-0 items-center gap-1.5">
                <li className="flex items-center gap-1.5">
                    <WorkflowIcon aria-hidden="true" className="size-3.5" />
                    <Link href={listHref} className="hover:text-foreground">
                        {state.workflowScope === "org" ? "Org Workflows" : "My Workflows"}
                    </Link>
                </li>
                <li aria-hidden="true">/</li>
                <li aria-current="page" className="truncate font-medium text-foreground">
                    {isEditing ? "Workflow Edit" : "Workflow Create"}
                </li>
            </ol>
        </nav>
    )
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
    const { state, handlers, isEditing, editingWorkflow } = controller
    const { workflowName, isSaving, hasServerErrors, workflowValidationError } = state
    const saveDisabled = isSaving || hasServerErrors || Boolean(workflowValidationError)
    const statusLabel = !isEditing ? "Draft" : editingWorkflow?.is_enabled ? "Enabled" : "Disabled"
    const [openedAt] = useState(() => new Date())
    const timestamp = formatEditorTimestamp(editingWorkflow ? new Date(editingWorkflow.created_at) : openedAt)

    return (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3">
            <div className="min-w-0 flex-1">
                <Input
                    aria-label="Workflow name"
                    value={workflowName}
                    onChange={(event) => handlers.setWorkflowName(event.target.value)}
                    placeholder="New Workflow"
                    className="h-7 w-full max-w-md border-none bg-transparent px-0 text-base font-semibold shadow-none focus-visible:ring-0 dark:bg-transparent"
                />
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span>{timestamp}</span>
                    <Badge variant="outline" className="h-4 rounded px-1.5 text-[10px] font-medium">
                        {statusLabel}
                    </Badge>
                </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
                {isEditing ? (
                    <SaveButton
                        reason={workflowValidationError}
                        variant="outline"
                        onClick={() => handlers.saveWorkflow({ isEnabled: true })}
                        disabled={saveDisabled}
                    >
                        {isSaving ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : <SaveIcon aria-hidden="true" />}
                        Save changes
                    </SaveButton>
                ) : (
                    <>
                        <SaveButton
                            reason={workflowValidationError}
                            variant="outline"
                            onClick={() => handlers.saveWorkflow({ isEnabled: false })}
                            disabled={saveDisabled}
                        >
                            <FolderIcon aria-hidden="true" />
                            Save draft
                        </SaveButton>
                        <SaveButton
                            reason={workflowValidationError}
                            variant="outline"
                            onClick={() => handlers.saveWorkflow({ isEnabled: true })}
                            disabled={saveDisabled}
                        >
                            {isSaving ? (
                                <Loader2Icon className="animate-spin" aria-hidden="true" />
                            ) : (
                                <SendIcon aria-hidden="true" />
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
        <div className="space-y-2">
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
        <div className="flex h-[calc(100dvh-4rem)] min-h-0 flex-col gap-3 bg-background px-4 pt-2 pb-4 sm:px-6">
            <WorkflowBreadcrumb controller={controller} />
            <WorkflowEditorHeader controller={controller} />
            <WorkflowEditorAlerts controller={controller} />
            {isCompact ? (
                <>
                    <div className="flex items-center justify-between gap-2">
                        <Button variant="outline" size="sm" onClick={() => setCompactPanel("inspector")}>
                            <SlidersHorizontalIcon aria-hidden="true" />
                            Configure
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setCompactPanel("build")}>
                            <PlusIcon aria-hidden="true" />
                            Add step
                        </Button>
                    </div>
                    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-border">
                        <WorkflowCanvas controller={controller} onSelect={selectNode} onRequestAddAction={requestAddAction} />
                    </div>
                    <Sheet open={compactPanel === "inspector"} onOpenChange={(open) => !open && setCompactPanel(null)}>
                        <SheetContent side="left" className="w-[min(100vw-2rem,22rem)] bg-muted/40 p-0">
                            <SheetHeader className="sr-only">
                                <SheetTitle>Configure step</SheetTitle>
                            </SheetHeader>
                            <div className="flex h-full min-h-0 flex-col p-2.5 pt-12">
                                <WorkflowInspector controller={controller} />
                            </div>
                        </SheetContent>
                    </Sheet>
                    <Sheet open={compactPanel === "build"} onOpenChange={(open) => !open && setCompactPanel(null)}>
                        <SheetContent side="right" className="w-[min(100vw-2rem,20rem)] p-0">
                            <SheetHeader className="sr-only">
                                <SheetTitle>Add step</SheetTitle>
                            </SheetHeader>
                            <div className="flex h-full min-h-0 flex-col p-2.5 pt-12">
                                <WorkflowBuildPanel
                                    controller={controller}
                                    onAddAction={addActionFromPalette}
                                    className="border-0 bg-transparent p-0"
                                />
                            </div>
                        </SheetContent>
                    </Sheet>
                </>
            ) : (
                <div className="grid min-h-0 flex-1 grid-cols-[17rem_minmax(0,1fr)_15rem] gap-2.5 rounded-xl border border-border bg-muted/30 p-2.5">
                    <WorkflowInspector controller={controller} />
                    <WorkflowCanvas controller={controller} onSelect={selectNode} onRequestAddAction={requestAddAction} />
                    <WorkflowBuildPanel controller={controller} onAddAction={addActionFromPalette} />
                </div>
            )}
        </div>
    )
}
