"use client"

import type { ReactNode } from "react"
import { ChevronUpIcon, GripVerticalIcon } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { cn } from "@/lib/utils"

/**
 * Compact control density for the editor side columns: 32px controls and 12px text, matching
 * the reference layout without changing the shared primitives.
 */
export const EDITOR_DENSITY_CLASS =
    "text-xs [&_[data-slot=select-trigger]]:h-8 [&_[data-slot=select-trigger]]:bg-card [&_[data-slot=select-trigger]]:px-2.5 [&_[data-slot=select-trigger]]:text-xs [&_input:not([type=checkbox]):not([type=radio])]:h-8 [&_input]:bg-card [&_input]:text-xs [&_textarea]:bg-card [&_textarea]:text-xs [&_label]:text-xs"

/** Side column: a scrolling stack of a heading row and section boxes. */
export function EditorColumn({
    children,
    className,
    ...props
}: { children: ReactNode; className?: string } & React.ComponentProps<"aside">) {
    return (
        <aside className={cn("flex min-h-0 flex-col gap-2 overflow-y-auto", EDITOR_DENSITY_CLASS, className)} {...props}>
            {children}
        </aside>
    )
}

/** Column heading row with a drag-handle glyph, as in the reference layout. */
export function PanelHeading({ title, actions }: { title: string; actions?: ReactNode }) {
    return (
        <div className="flex h-10 shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-2.5">
            <GripVerticalIcon aria-hidden="true" className="size-3.5 text-muted-foreground" />
            <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</h2>
            {actions}
        </div>
    )
}

/** Bordered section box with an uppercase caption and a collapse chevron. */
export function PanelSection({
    title,
    children,
    actions,
    defaultOpen = true,
}: {
    title: string
    children: ReactNode
    actions?: ReactNode
    defaultOpen?: boolean
}) {
    return (
        <Collapsible defaultOpen={defaultOpen} className="shrink-0 rounded-lg border border-border bg-card">
            <div className="flex h-8 items-center gap-1 pr-1.5">
                <CollapsibleTrigger className="group/section flex h-full min-w-0 flex-1 items-center justify-between gap-2 px-2.5 text-left text-[10px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
                    <span className="truncate">{title}</span>
                    <ChevronUpIcon
                        aria-hidden="true"
                        className="size-3 shrink-0 rotate-180 transition-transform group-data-panel-open/section:rotate-0"
                    />
                </CollapsibleTrigger>
                {actions}
            </div>
            <CollapsibleContent>
                <div className="space-y-2 px-2 pb-2">{children}</div>
            </CollapsibleContent>
        </Collapsible>
    )
}

/** Muted inner card inside a section: icon, title, chevron, then its own content. */
export function PanelCard({
    icon: Icon,
    title,
    children,
    actions,
    defaultOpen = true,
}: {
    icon: React.ElementType
    title: ReactNode
    children?: ReactNode
    actions?: ReactNode
    defaultOpen?: boolean
}) {
    return (
        <Collapsible defaultOpen={defaultOpen} className="rounded-md bg-muted/70 dark:bg-muted/40">
            <div className="flex h-8 items-center gap-1 pr-1">
                <CollapsibleTrigger className="group/card flex h-full min-w-0 flex-1 items-center gap-2 px-2.5 text-left text-xs font-medium">
                    <Icon aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 truncate">{title}</span>
                    {children ? (
                        <ChevronUpIcon
                            aria-hidden="true"
                            className="size-3 shrink-0 rotate-180 text-muted-foreground transition-transform group-data-panel-open/card:rotate-0"
                        />
                    ) : null}
                </CollapsibleTrigger>
                {actions}
            </div>
            {children ? (
                <CollapsibleContent>
                    <div className="space-y-2 px-2.5 pb-2.5">{children}</div>
                </CollapsibleContent>
            ) : null}
        </Collapsible>
    )
}

/** Radio options drawn as the reference's small dots: filled for the chosen one. */
export function DotOptionGroup({
    ariaLabel,
    value,
    options,
    onValueChange,
    disabled = false,
}: {
    ariaLabel: string
    value: string
    options: { value: string; label: string }[]
    onValueChange: (value: string) => void
    disabled?: boolean
}) {
    return (
        <RadioGroup
            aria-label={ariaLabel}
            value={value}
            onValueChange={(next) => typeof next === "string" && next && onValueChange(next)}
            disabled={disabled}
            className="gap-0"
        >
            {options.map((option) => (
                <label
                    key={option.value}
                    className={cn(
                        "flex cursor-pointer items-center gap-2 rounded px-0.5 py-1 text-xs",
                        option.value === value ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                        disabled && "cursor-default",
                    )}
                >
                    <RadioGroupItem
                        value={option.value}
                        className="size-1.5 border-0 bg-muted-foreground/25 after:-inset-2 data-checked:bg-primary dark:bg-muted-foreground/30 dark:data-checked:bg-primary [&_[data-slot=radio-group-indicator]]:hidden"
                    />
                    <span>{option.label}</span>
                </label>
            ))}
        </RadioGroup>
    )
}
