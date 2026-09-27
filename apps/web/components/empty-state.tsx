import * as React from "react"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, type EmptyTitleHeadingLevel } from "@/components/ui/empty"
import { cn } from "@/lib/utils"

type EmptyStateBaseProps = {
    /** Neutral icon for the missing item (CalendarIcon, CheckSquareIcon, BellIcon); never an alert icon. */
    icon: LucideIcon
    title: string
    /** Heading semantics for the title, when it replaces markup that used a heading. */
    headingLevel?: EmptyTitleHeadingLevel | undefined
    className?: string | undefined
}

type FirstRunEmptyStateProps = EmptyStateBaseProps & {
    /** One action that creates the missing item. Omit when the viewer cannot create it. */
    action?: React.ReactNode
    onClearFilters?: never
}

type FilteredEmptyStateProps = EmptyStateBaseProps & {
    /** Filters or search are active: renders "Clear filters" instead of a create action. */
    onClearFilters: () => void
    action?: never
}

type EmptyStateProps = FirstRunEmptyStateProps | FilteredEmptyStateProps

/**
 * Empty list or section. First-run: icon, title, optional create action.
 * Filtered: icon, title ("No matching agencies"), Clear filters.
 */
function EmptyState({ icon: Icon, title, headingLevel, action, onClearFilters, className }: EmptyStateProps) {
    return (
        <Empty data-slot="empty-state" className={cn("gap-3 px-6 py-10", className)}>
            <EmptyHeader>
                <EmptyMedia variant="icon">
                    <Icon aria-hidden="true" />
                </EmptyMedia>
                <EmptyTitle headingLevel={headingLevel} className="text-base">
                    {title}
                </EmptyTitle>
            </EmptyHeader>
            {onClearFilters ? (
                <Button variant="outline" size="sm" onClick={onClearFilters}>
                    Clear filters
                </Button>
            ) : (
                action
            )}
        </Empty>
    )
}

export { EmptyState }
export type { EmptyStateProps }
