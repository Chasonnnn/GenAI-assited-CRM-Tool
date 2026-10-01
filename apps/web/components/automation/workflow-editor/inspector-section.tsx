"use client"

import type { ReactNode } from "react"
import { ChevronDownIcon } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"

/** Collapsible group inside the editor side panels: uppercase caption with a chevron. */
export function InspectorSection({
    title,
    children,
    defaultOpen = true,
    className,
}: {
    title: string
    children: ReactNode
    defaultOpen?: boolean
    className?: string
}) {
    return (
        <Collapsible defaultOpen={defaultOpen} className={cn("border-b border-border last:border-b-0", className)}>
            <CollapsibleTrigger className="group/section flex w-full items-center justify-between px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground">
                <span>{title}</span>
                <ChevronDownIcon
                    aria-hidden="true"
                    className="size-3.5 transition-transform group-data-panel-open/section:rotate-180"
                />
            </CollapsibleTrigger>
            <CollapsibleContent>
                <div className="space-y-3 px-4 pb-4">{children}</div>
            </CollapsibleContent>
        </Collapsible>
    )
}

/** Side panel shell: fixed header row with a drag-handle glyph, scrolling body. */
export function InspectorPanel({
    title,
    icon,
    actions,
    children,
    className,
    ...props
}: {
    title: string
    icon: ReactNode
    actions?: ReactNode
    children: ReactNode
    className?: string
} & Omit<React.ComponentProps<"section">, "title">) {
    return (
        <section
            className={cn("flex min-h-0 flex-col rounded-xl border border-border bg-card shadow-xs", className)}
            {...props}
        >
            <header className="flex h-11 shrink-0 items-center gap-2 border-b border-border px-3">
                {icon}
                <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</h2>
                {actions}
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </section>
    )
}
