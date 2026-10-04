"use client"

import { useEffect, useEffectEvent, useRef, useState } from "react"
import type { ReactNode } from "react"
import { useRouter } from "next/navigation"
import {
    AlertCircleIcon,
    ChevronLeftIcon,
    FolderIcon,
    Loader2Icon,
    PlusIcon,
    Redo2Icon,
    SaveIcon,
    SendIcon,
    SlidersHorizontalIcon,
    Undo2Icon,
} from "lucide-react"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useMediaQuery } from "@/hooks/use-media-query"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import { useWorkflowTestRun, type WorkflowTestRunController } from "@/lib/workflows/use-workflow-test-run"
import { ReasonButton } from "./reason-button"
import { useStepDrag } from "./use-step-drag"
import { WorkflowBuildPanel } from "./workflow-build-panel"
import { WorkflowCanvas } from "./workflow-canvas"
import { WorkflowInspector } from "./workflow-inspector"
import { WorkflowTestRunBar, WorkflowTestRunButton } from "./workflow-test-run"

// Side panels stack into sheets below the lg breakpoint, where they would cover the canvas.
const COMPACT_LAYOUT_QUERY = "(max-width: 1023px)"
// Below xl the palette starts collapsed so steps keep room between the floating panels.
const NARROW_CANVAS_QUERY = "(max-width: 1279px)"
// Canvas padding that keeps steps centered between the floating palette and inspector.
const PALETTE_INSET = "17rem"
const INSPECTOR_INSET = "25rem"

// Phones give each save button an equal share of the actions row.
const SAVE_BUTTON_CLASS = "flex-1 sm:flex-none"

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)

const FLOATING_PANEL_CLASS =
    "absolute z-20 flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-popover/95 text-popover-foreground shadow-[0_12px_32px_rgb(0_0_0/0.08),0_2px_6px_rgb(0_0_0/0.06)] backdrop-blur-md"

/** Typing in a field keeps its own undo and delete keys. */
function isEditableTarget(target: EventTarget | null): boolean {
    return (
        target instanceof Element &&
        Boolean(target.closest("input, textarea, select, [contenteditable='true'], [role='menu'], [role='dialog'], [role='listbox']"))
    )
}

function IconAction({
    label,
    shortcut,
    shortcutLabel,
    disabled,
    onClick,
    children,
}: {
    label: string
    /** aria-keyshortcuts value, e.g. "Meta+Z". */
    shortcut: string
    shortcutLabel: string
    disabled: boolean
    onClick: () => void
    children: ReactNode
}) {
    return (
        <Tooltip>
            <TooltipTrigger
                render={
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        className="size-8"
                        aria-label={label}
                        aria-keyshortcuts={shortcut}
                        disabled={disabled}
                        onClick={onClick}
                    />
                }
            >
                {children}
            </TooltipTrigger>
            <TooltipContent>
                {label} <span className="text-muted-foreground">{shortcutLabel}</span>
            </TooltipContent>
        </Tooltip>
    )
}

function WorkflowEditorToolbar({
    controller,
    testRun,
}: {
    controller: WorkflowEditorController
    testRun: WorkflowTestRunController
}) {
    const router = useRouter()
    const { state, handlers, history, isEditing, editingWorkflow, listHref } = controller
    const { workflowName, isSaving, hasServerErrors, workflowValidationError } = state
    const saveDisabled = isSaving || hasServerErrors || Boolean(workflowValidationError)
    const statusLabel = !isEditing ? "Draft" : editingWorkflow?.is_enabled ? "Enabled" : "Disabled"
    const modifier = IS_MAC ? "Meta" : "Control"
    const modifierLabel = IS_MAC ? "⌘" : "Ctrl+"

    return (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-border bg-card px-2 py-1.5">
            <nav aria-label="Breadcrumb" className="flex min-w-0 flex-[1_1_16rem] items-center gap-1.5">
                <Button variant="ghost" size="icon-sm" className="size-8" aria-label="Go back" onClick={() => router.back()}>
                    <ChevronLeftIcon aria-hidden="true" />
                </Button>
                <Link href={listHref} className="shrink-0 text-xs text-muted-foreground hover:text-foreground">
                    {state.workflowScope === "org" ? "Org Workflows" : "My Workflows"}
                </Link>
                <span aria-hidden="true" className="text-xs text-muted-foreground">
                    /
                </span>
                <Input
                    aria-label="Workflow name"
                    value={workflowName}
                    onChange={(event) => handlers.setWorkflowName(event.target.value)}
                    placeholder="New Workflow"
                    className="h-8 min-w-32 flex-1 border-none bg-transparent px-1 text-sm font-semibold shadow-none focus-visible:ring-2 dark:bg-transparent"
                />
                <Badge variant="outline" className="h-5 shrink-0 rounded-full px-2 text-[11px] font-medium">
                    {statusLabel}
                </Badge>
            </nav>
            <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto">
                <IconAction
                    label="Undo"
                    shortcut={`${modifier}+Z`}
                    shortcutLabel={`${modifierLabel}Z`}
                    disabled={!history.canUndo} onClick={handlers.undo}>
                    <Undo2Icon aria-hidden="true" />
                </IconAction>
                <IconAction
                    label="Redo"
                    shortcut={`${modifier}+Shift+Z`}
                    shortcutLabel={`${modifierLabel}⇧Z`}
                    disabled={!history.canRedo} onClick={handlers.redo}>
                    <Redo2Icon aria-hidden="true" />
                </IconAction>
                <span aria-hidden="true" className="mx-1 h-5 w-px bg-border" />
                <WorkflowTestRunButton testRun={testRun} disabledReason={workflowValidationError} />
                {isEditing ? (
                    <ReasonButton
                        className={SAVE_BUTTON_CLASS}
                        reason={workflowValidationError}
                        onClick={() => handlers.saveWorkflow({ isEnabled: true })}
                        disabled={saveDisabled}
                    >
                        {isSaving ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : <SaveIcon aria-hidden="true" />}
                        Save changes
                    </ReasonButton>
                ) : (
                    <>
                        <ReasonButton
                            className={SAVE_BUTTON_CLASS}
                            reason={workflowValidationError}
                            variant="outline"
                            onClick={() => handlers.saveWorkflow({ isEnabled: false })}
                            disabled={saveDisabled}
                        >
                            <FolderIcon aria-hidden="true" />
                            Save draft
                        </ReasonButton>
                        <ReasonButton
                            className={SAVE_BUTTON_CLASS}
                            reason={workflowValidationError}
                            onClick={() => handlers.saveWorkflow({ isEnabled: true })}
                            disabled={saveDisabled}
                        >
                            {isSaving ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : <SendIcon aria-hidden="true" />}
                            Launch workflow
                        </ReasonButton>
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
    const isNarrowCanvas = useMediaQuery(NARROW_CANVAS_QUERY)
    const [compactPanel, setCompactPanel] = useState<"inspector" | "build" | null>(null)
    const [paletteCollapsedOverride, setPaletteCollapsedOverride] = useState<boolean | null>(null)
    const paletteCollapsed = paletteCollapsedOverride ?? isNarrowCanvas
    const canvasRef = useRef<HTMLDivElement>(null)
    const testRun = useWorkflowTestRun(controller)
    const { selection, selectedActionIndex, setSelection, handlers, state } = controller
    const inspectorOpen = selection.kind !== "none"

    const revealStep = (index: number) => {
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
        // The new or next node renders on the following frame.
        window.requestAnimationFrame(() => {
            canvasRef.current
                ?.querySelector(`[data-step-index="${index}"]`)
                ?.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" })
        })
    }

    const selectNode = (next: WorkflowEditorSelection) => {
        setSelection(next)
        if (isCompact) setCompactPanel(next.kind === "none" ? null : "inspector")
    }
    const insertAction = (actionType: string, index: number) => {
        handlers.addAction(actionType, index)
        revealStep(index)
        if (isCompact) setCompactPanel("inspector")
    }
    /** Palette clicks add after the selected step, or at the end when nothing is selected. */
    const addActionFromPalette = (actionType: string) => {
        const index =
            selection.kind === "action" ? selectedActionIndex + 1 : selection.kind === "trigger" ? 0 : state.actions.length
        insertAction(actionType, index)
    }
    const requestAddAction = () => {
        if (isCompact) {
            setCompactPanel("build")
            return
        }
        handlers.addAction()
        revealStep(state.actions.length)
    }
    const insertBlankAt = (index: number) => {
        handlers.addAction("", index)
        revealStep(index)
        if (isCompact) setCompactPanel("inspector")
    }

    const { drag, begin } = useStepDrag({
        canvasRef,
        onInsert: insertAction,
        onReorder: (from, to) => {
            handlers.reorderAction(from, to)
            revealStep(to)
        },
    })

    const handleShortcut = useEffectEvent((event: KeyboardEvent) => {
        if (event.defaultPrevented || isEditableTarget(event.target)) return
        const key = event.key.toLowerCase()
        if ((event.metaKey || event.ctrlKey) && (key === "z" || key === "y")) {
            event.preventDefault()
            if (key === "y" || event.shiftKey) handlers.redo()
            else handlers.undo()
            return
        }
        const index = selection.kind === "action" ? selectedActionIndex : -1
        if ((key === "delete" || key === "backspace") && index >= 0) {
            event.preventDefault()
            handlers.removeAction(index)
            return
        }
        if (event.altKey && (key === "arrowup" || key === "arrowdown") && index >= 0) {
            event.preventDefault()
            handlers.moveAction(index, key === "arrowup" ? -1 : 1)
            return
        }
        if (key === "escape" && selection.kind !== "none") selectNode({ kind: "none" })
    })
    useEffect(() => {
        const listener = (event: KeyboardEvent) => handleShortcut(event)
        window.addEventListener("keydown", listener)
        return () => window.removeEventListener("keydown", listener)
    }, [])

    const canvas = (
        <WorkflowCanvas
            controller={controller}
            testRun={testRun}
            drag={drag}
            canvasRef={canvasRef}
            insetLeft={!isCompact && !paletteCollapsed ? PALETTE_INSET : "1rem"}
            insetRight={!isCompact && inspectorOpen ? INSPECTOR_INSET : "1rem"}
            onSelect={selectNode}
            onRequestAddAction={requestAddAction}
            onInsertAt={insertBlankAt}
            onStepPointerDown={(index, label, event) => begin(event, { kind: "step", index }, label)}
        />
    )

    return (
        <div className="flex h-[calc(100dvh-4rem)] min-h-0 flex-col gap-2.5 bg-background px-4 pt-2 pb-4 sm:px-6">
            <WorkflowEditorToolbar controller={controller} testRun={testRun} />
            <WorkflowEditorAlerts controller={controller} />
            {isCompact ? (
                <div className="flex items-center justify-between gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                            if (selection.kind === "none") setSelection({ kind: "trigger" })
                            setCompactPanel("inspector")
                        }}
                    >
                        <SlidersHorizontalIcon aria-hidden="true" />
                        Configure
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setCompactPanel("build")}>
                        <PlusIcon aria-hidden="true" />
                        Add step
                    </Button>
                </div>
            ) : null}
            <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
                {canvas}
                {!isCompact ? (
                    <WorkflowBuildPanel
                        controller={controller}
                        onAddAction={addActionFromPalette}
                        onItemPointerDown={(actionType, label, event) =>
                            begin(event, { kind: "palette", actionType }, label)
                        }
                        collapsed={paletteCollapsed}
                        onToggleCollapsed={() => setPaletteCollapsedOverride(!paletteCollapsed)}
                        className={`${FLOATING_PANEL_CLASS} top-3 left-3 max-h-[calc(100%-1.5rem)] w-60`}
                    />
                ) : null}
                {!isCompact && inspectorOpen ? (
                    <WorkflowInspector
                        controller={controller}
                        onSelect={selectNode}
                        onClose={() => selectNode({ kind: "none" })}
                        onRevealStep={revealStep}
                        className={`${FLOATING_PANEL_CLASS} top-3 right-3 bottom-3 w-[min(23.5rem,calc(100%-1.5rem))] animate-in fade-in-0 slide-in-from-right-2 motion-reduce:animate-none`}
                    />
                ) : null}
                <WorkflowTestRunBar testRun={testRun} className="absolute bottom-3 left-1/2 z-30 -translate-x-1/2" />
            </div>

            {drag ? (
                <div
                    aria-hidden="true"
                    style={{ transform: `translate(${drag.pointer.x + 12}px, ${drag.pointer.y + 12}px)` }}
                    className="pointer-events-none fixed top-0 left-0 z-50 flex h-8 items-center gap-2 rounded-lg border border-border bg-popover px-3 text-xs font-medium shadow-lg"
                >
                    {drag.label}
                </div>
            ) : null}
            {drag ? <div aria-hidden="true" className="fixed inset-0 z-40 cursor-grabbing" /> : null}

            {isCompact ? (
                <>
                    <Sheet open={compactPanel === "inspector"} onOpenChange={(open) => !open && setCompactPanel(null)}>
                        <SheetContent side="left" className="w-[min(100vw-2rem,24rem)] p-0">
                            <SheetHeader className="sr-only">
                                <SheetTitle>Configure step</SheetTitle>
                            </SheetHeader>
                            <div className="flex h-full min-h-0 flex-col pt-10">
                                <WorkflowInspector controller={controller} onSelect={selectNode} onRevealStep={revealStep} />
                            </div>
                        </SheetContent>
                    </Sheet>
                    <Sheet open={compactPanel === "build"} onOpenChange={(open) => !open && setCompactPanel(null)}>
                        <SheetContent side="right" className="w-[min(100vw-2rem,20rem)] p-0">
                            <SheetHeader className="sr-only">
                                <SheetTitle>Add step</SheetTitle>
                            </SheetHeader>
                            <div className="flex h-full min-h-0 flex-col p-2.5 pt-12">
                                <WorkflowBuildPanel controller={controller} onAddAction={addActionFromPalette} />
                            </div>
                        </SheetContent>
                    </Sheet>
                </>
            ) : null}
        </div>
    )
}
