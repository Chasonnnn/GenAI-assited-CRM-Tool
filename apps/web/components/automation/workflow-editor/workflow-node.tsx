"use client"

import type { CSSProperties, ElementType, PointerEvent as ReactPointerEvent, ReactNode } from "react"
import { AlertCircleIcon, CheckIcon, GripVerticalIcon, ShieldCheckIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { TestRunStepState } from "@/lib/workflows/use-workflow-test-run"
import { TEST_RUN_STEP_LABELS } from "@/lib/workflows/use-workflow-test-run"
import { cn } from "@/lib/utils"
import { NODE_TONE_CLASSES, type ActionTone } from "./node-meta"

export const NODE_WIDTH_CLASS = "w-80 max-w-[calc(100vw-3rem)]"

const STEP_STATE_CLASSES: Record<TestRunStepState, string> = {
    would_run: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
    needs_approval: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    after_approval: "bg-muted text-muted-foreground",
    skipped: "bg-muted text-muted-foreground",
}

/** Result chip from the last test run; chips appear one after another down the chain. */
export function StepStateChip({ state, order }: { state: TestRunStepState; order: number }) {
    return (
        <span
            style={{ animationDelay: `${order * 90}ms` } as CSSProperties}
            className={cn(
                "flex h-5 shrink-0 items-center gap-1 rounded-full px-2 text-[11px] font-medium animate-in fade-in-0 slide-in-from-top-1 fill-mode-both motion-reduce:animate-none",
                STEP_STATE_CLASSES[state],
            )}
        >
            <span
                aria-hidden="true"
                className={cn(
                    "size-1.5 rounded-full bg-current",
                    state === "after_approval" || state === "skipped" ? "opacity-50" : null,
                )}
            />
            {TEST_RUN_STEP_LABELS[state]}
        </span>
    )
}

/** A filter line in the trigger node; after a test run it shows pass or fail and the record's value. */
export function CriterionLine({ text, result }: { text: string; result?: { passed: boolean; actual: string } }) {
    if (!result) return <li className="truncate">{text}</li>
    const Icon = result.passed ? CheckIcon : XIcon
    return (
        <li className="flex min-w-0 items-start gap-1.5">
            <Icon
                aria-hidden="true"
                className={cn(
                    "mt-0.5 size-3 shrink-0",
                    result.passed ? "text-emerald-600 dark:text-emerald-400" : "text-destructive",
                )}
            />
            <span className="min-w-0">
                <span className="block truncate">{text}</span>
                <span className="block truncate text-muted-foreground">
                    {result.passed ? "Matched" : "Not matched"} · record has {result.actual === "None" ? "no value" : result.actual}
                </span>
            </span>
        </li>
    )
}

/**
 * One step on the canvas: a tinted shell with the step type over a card body. The whole node is
 * the select button; pressing and moving it starts a drag when onDragStart is given.
 */
export function WorkflowNode({
    icon: Icon,
    tone,
    typeLabel,
    ariaLabel,
    selected,
    dragging = false,
    tag,
    trailing,
    stepState,
    stepOrder = 0,
    title,
    subtitle,
    issue,
    requiresApproval = false,
    footer,
    hasInput = true,
    onSelect,
    onDragStart,
    stepIndex,
}: {
    icon: ElementType
    tone: ActionTone
    typeLabel: string
    ariaLabel: string
    selected: boolean
    dragging?: boolean
    tag?: string
    /** Controls drawn over the node, outside the select button. */
    trailing?: ReactNode
    stepState?: TestRunStepState | null
    stepOrder?: number
    title: string
    subtitle?: string | null
    issue?: string | null
    requiresApproval?: boolean
    footer?: ReactNode
    hasInput?: boolean
    onSelect: () => void
    onDragStart?: (event: ReactPointerEvent) => void
    stepIndex?: number
}) {
    const toneClasses = NODE_TONE_CLASSES[tone]
    return (
        <div
            className={cn("group/node relative", NODE_WIDTH_CLASS, dragging && "opacity-40")}
            {...(stepIndex === undefined ? {} : { "data-step-index": stepIndex })}
        >
            {hasInput ? (
                <span
                    aria-hidden="true"
                    className={cn("absolute -top-1 left-1/2 z-10 size-2 -translate-x-1/2 rounded-full ring-2 ring-background", toneClasses.dot)}
                />
            ) : null}
            <Button
                unstyled
                type="button"
                aria-label={ariaLabel}
                aria-pressed={selected}
                onClick={onSelect}
                onPointerDown={onDragStart}
                className={cn(
                    "flex w-full flex-col gap-1 rounded-xl border p-1 pb-1.5 text-left shadow-[0_1px_2px_rgb(0_0_0/0.04)] outline-none backdrop-blur-sm transition-[border-color,box-shadow] duration-150 focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    toneClasses.shell,
                    onDragStart && "cursor-grab active:cursor-grabbing",
                    selected ? "ring-2 ring-primary/40" : "hover:shadow-[0_6px_16px_rgb(0_0_0/0.06)]",
                )}
            >
                <span className="flex h-7 w-full items-center gap-2 px-1.5">
                    <Icon aria-hidden="true" className={cn("size-4 shrink-0", toneClasses.label)} />
                    <span className={cn("min-w-0 flex-1 truncate text-[13px] font-medium", toneClasses.label)}>
                        {typeLabel}
                    </span>
                    {stepState ? <StepStateChip state={stepState} order={stepOrder} /> : null}
                    {tag ? (
                        <span className="rounded-full bg-background/70 px-2 py-px text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">
                            {tag}
                        </span>
                    ) : null}
                    {onDragStart && !stepState ? (
                        <GripVerticalIcon
                            aria-hidden="true"
                            className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover/node:opacity-100"
                        />
                    ) : null}
                </span>
                <span className="flex w-full flex-col gap-0.5 rounded-lg bg-card px-3 py-2.5">
                    <span className="truncate text-sm font-semibold">{title}</span>
                    {subtitle ? <span className="truncate text-xs text-muted-foreground">{subtitle}</span> : null}
                    {issue ? (
                        <span className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400">
                            <AlertCircleIcon aria-hidden="true" className="size-3 shrink-0" />
                            <span className="truncate">{issue}</span>
                        </span>
                    ) : null}
                    {requiresApproval ? (
                        <span className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400">
                            <ShieldCheckIcon aria-hidden="true" className="size-3 shrink-0" />
                            Requires approval
                        </span>
                    ) : null}
                    {footer}
                </span>
            </Button>
            <span
                aria-hidden="true"
                className={cn("absolute -bottom-1 left-1/2 z-10 size-2 -translate-x-1/2 rounded-full ring-2 ring-background", toneClasses.dot)}
            />
            {trailing}
        </div>
    )
}
