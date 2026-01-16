"use client"

import { TableHead } from "@/components/ui/table"
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react"
import { cn } from "@/lib/utils"

interface SortableTableHeadProps {
    column: string
    label: string
    currentSort: string | null
    currentOrder: "asc" | "desc"
    onSort: (column: string) => void
    className?: string
}

/**
 * Sortable table header with flip icon.
 * Click toggles between ascending and descending.
 */
export function SortableTableHead({
    column,
    label,
    currentSort,
    currentOrder,
    onSort,
    className,
}: SortableTableHeadProps) {
    const isActive = currentSort === column

    const handleClick = () => {
        onSort(column)
    }

    const renderIcon = () => {
        if (!isActive) {
            return <ArrowUpDown className="size-4 text-muted-foreground/50" />
        }
        return currentOrder === "asc" ? (
            <ArrowUp className="size-4 text-foreground" />
        ) : (
            <ArrowDown className="size-4 text-foreground" />
        )
    }

    return (
        <TableHead
            className={cn(
                "cursor-pointer select-none hover:bg-muted/50 transition-colors",
                className
            )}
            onClick={handleClick}
        >
            <div className="inline-flex w-full items-center justify-center gap-1">
                <span className="invisible">{renderIcon()}</span>
                <span>{label}</span>
                <span>{renderIcon()}</span>
            </div>
        </TableHead>
    )
}
