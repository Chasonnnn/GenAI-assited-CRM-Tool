"use client"

import { cn } from "@/lib/utils"

interface RichTextEditorLoadingProps {
    className: string | undefined
    minHeight: string
    showSubmit: boolean
}

export function RichTextEditorLoading({
    className,
    minHeight,
    showSubmit,
}: RichTextEditorLoadingProps) {
    return (
        <div className={cn("border rounded-md", className)}>
            <div className="flex h-10 items-center gap-1 border-b bg-muted/30 px-2 py-1.5">
                <div className="size-6 animate-pulse rounded bg-muted" />
                <div className="size-6 animate-pulse rounded bg-muted" />
                <div className="size-6 animate-pulse rounded bg-muted" />
                {showSubmit && <div className="ml-auto h-7 w-16 animate-pulse rounded bg-muted" />}
            </div>
            <div className="px-3 py-2" style={{ minHeight }}>
                <div className="h-4 w-3/4 animate-pulse rounded bg-muted/50" />
            </div>
        </div>
    )
}
