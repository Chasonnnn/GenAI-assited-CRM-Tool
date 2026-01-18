"use client"

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type PaginationJumpProps = {
    page: number
    totalPages: number
    onPageChange: (page: number) => void
    className?: string
}

export function PaginationJump({ page, totalPages, onPageChange, className }: PaginationJumpProps) {
    const [pageInput, setPageInput] = useState(String(page))

    useEffect(() => {
        setPageInput(String(page))
    }, [page])

    const commitPage = () => {
        const parsed = Number(pageInput)
        if (!Number.isFinite(parsed)) {
            setPageInput(String(page))
            return
        }
        const nextPage = Math.min(Math.max(1, Math.floor(parsed)), totalPages)
        if (nextPage !== page) {
            onPageChange(nextPage)
        } else {
            setPageInput(String(nextPage))
        }
    }

    const canCommit = totalPages > 1

    return (
        <div className={cn("flex items-center gap-2", className)}>
            <span className="text-xs text-muted-foreground">Page</span>
            <Input
                aria-label="Page number"
                type="number"
                min={1}
                max={totalPages}
                value={pageInput}
                onChange={(event) => setPageInput(event.target.value)}
                onKeyDown={(event) => {
                    if (event.key === "Enter") {
                        commitPage()
                    }
                }}
                className="h-8 w-16 text-center"
                disabled={!canCommit}
            />
            <span className="text-xs text-muted-foreground">of {totalPages}</span>
            <Button variant="outline" size="sm" onClick={commitPage} disabled={!canCommit}>
                Go
            </Button>
        </div>
    )
}
