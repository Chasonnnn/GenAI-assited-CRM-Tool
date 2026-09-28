"use client"

import type * as React from "react"
import { SearchIcon, SlidersHorizontalIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

type FilterChip = {
    key: string
    label: string
    onRemove: () => void
}

/** Falsy entries are skipped, so pages can pass `[stage !== "all" && { ... }, ...]`. */
type FilterChipList = ReadonlyArray<FilterChip | false | null | undefined>

type ListToolbarProps = {
    filters?: React.ReactNode
    search?: React.ReactNode
    chips?: FilterChipList | undefined
    onReset?: (() => void) | undefined
    className?: string | undefined
}

/**
 * List filter bar: primary filters (Stage, Date, More Filters) on the left, search on the
 * right from xl, and a row of active-filter chips with Reset. Pages own filter state and
 * URL sync; this component only lays it out.
 */
function ListToolbar({ filters, search, chips = [], onReset, className }: ListToolbarProps) {
    return (
        <div data-slot="list-toolbar" className={cn("flex-shrink-0 border-b border-border px-6 py-3", className)}>
            <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
                    {filters ? <div className="flex flex-wrap items-center gap-3">{filters}</div> : null}
                    {search}
                </div>
                <FilterChips chips={chips} onReset={onReset} />
            </div>
        </div>
    )
}

function ListToolbarSearch({
    value,
    onValueChange,
    placeholder,
    "aria-label": ariaLabel,
    type = "text",
    className,
}: {
    value: string
    onValueChange: (value: string) => void
    placeholder: string
    "aria-label": string
    /** "search" gives the input the searchbox role. */
    type?: "text" | "search"
    className?: string
}) {
    return (
        <div className={cn("relative w-full xl:ml-auto xl:w-[320px] xl:flex-none", className)}>
            <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
                type={type}
                placeholder={placeholder}
                value={value}
                onChange={(event) => onValueChange(event.target.value)}
                className="pl-9"
                aria-label={ariaLabel}
            />
        </div>
    )
}

/** "More Filters" popover. `active` marks the trigger when any secondary filter is set. */
function MoreFiltersPopover({
    open,
    onOpenChange,
    active = false,
    disabled = false,
    children,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    active?: boolean
    disabled?: boolean
    children: React.ReactNode
}) {
    return (
        <Popover open={open} onOpenChange={onOpenChange}>
            <PopoverTrigger
                type="button"
                aria-label="More Filters"
                disabled={disabled}
                data-active={active ? "" : undefined}
                className={buttonVariants({
                    variant: "outline",
                    className: cn(
                        "justify-between border-border/70 bg-background/85 shadow-xs backdrop-blur-sm",
                        active && "border-foreground/15 bg-accent/40 text-foreground shadow-sm"
                    ),
                })}
            >
                <SlidersHorizontalIcon className="size-4" />
                More Filters
            </PopoverTrigger>
            <PopoverContent
                align="end"
                className="w-[min(24rem,calc(100vw-2rem))] gap-4 border border-border/70 bg-background/95 p-4 backdrop-blur-xl"
            >
                <div className="grid gap-4">{children}</div>
            </PopoverContent>
        </Popover>
    )
}

/** Active-filter chips plus Reset. Renders nothing when no filter is active. */
function FilterChips({
    chips,
    onReset,
    className,
}: {
    chips: FilterChipList
    onReset?: (() => void) | undefined
    className?: string | undefined
}) {
    const activeChips = chips.filter((chip): chip is FilterChip => Boolean(chip))
    if (activeChips.length === 0) return null

    return (
        <div data-slot="filter-chips" className={cn("flex flex-wrap items-center gap-2", className)}>
            {activeChips.map((chip) => (
                <Button
                    key={chip.key}
                    variant="outline"
                    size="sm"
                    onClick={chip.onRemove}
                    className="gap-2"
                    aria-label={`Remove filter: ${chip.label}`}
                >
                    {chip.label}
                    <XIcon className="size-3" />
                </Button>
            ))}
            {onReset ? (
                <Button variant="ghost" size="sm" onClick={onReset}>
                    Reset
                </Button>
            ) : null}
        </div>
    )
}

export { FilterChips, ListToolbar, ListToolbarSearch, MoreFiltersPopover }
export type { FilterChip, FilterChipList, ListToolbarProps }
