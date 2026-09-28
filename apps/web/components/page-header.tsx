"use client"

import type * as React from "react"
import { ArrowLeftIcon } from "lucide-react"

import Link from "@/components/app-link"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type PageHeaderProps = {
    /** Must match the sidebar label for top-level pages. */
    title: React.ReactNode
    /** Leading back button for detail and editor pages. Top-level pages leave it unset. */
    back?: { href: string; label: string } | undefined
    /** Inline status after the title, such as a status badge or save state. */
    meta?: React.ReactNode
    /**
     * Right-aligned actions. They wrap below the title when the row is too narrow and then
     * span the full row, so buttons with `flex-1 sm:flex-none` share it evenly.
     */
    actions?: React.ReactNode
    sticky?: boolean | undefined
    className?: string | undefined
}

/**
 * Page header bar: 64px band with a 24px h1, optional back button,
 * inline meta and right-aligned actions. Page content goes below it in a `p-6` wrapper.
 */
function PageHeader({
    title,
    back,
    meta,
    actions,
    sticky = false,
    className,
}: PageHeaderProps) {
    return (
        <div
            data-slot="page-header"
            className={cn(
                "shrink-0 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
                sticky && "sticky top-0 z-20",
                className,
            )}
        >
            <div className="flex min-h-16 flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3">
                <div className="flex min-w-0 max-w-full items-center gap-2">
                    {back ? (
                        <Button
                            variant="ghost"
                            size="icon-sm"
                            className="-ml-2"
                            aria-label={back.label}
                            render={<Link href={back.href} />}
                        >
                            <ArrowLeftIcon aria-hidden="true" />
                        </Button>
                    ) : null}
                    <h1 className="truncate text-2xl font-semibold">{title}</h1>
                    {meta}
                </div>
                {actions ? (
                    <div
                        data-slot="page-header-actions"
                        className="ml-auto flex grow flex-wrap items-center justify-end gap-2"
                    >
                        {actions}
                    </div>
                ) : null}
            </div>
        </div>
    )
}

export { PageHeader }
export type { PageHeaderProps }
