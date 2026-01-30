"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { XIcon, SendIcon, Loader2Icon } from "lucide-react"

interface PendingCommentInputProps {
    anchorText: string
    onSubmit: (content: string) => void
    onCancel: () => void
    isSubmitting: boolean
}

export function PendingCommentInput({
    anchorText,
    onSubmit,
    onCancel,
    isSubmitting
}: PendingCommentInputProps) {
    const [content, setContent] = useState("")

    return (
        <div className="bg-card border border-teal-500 rounded-lg p-3 space-y-2 shadow-md mb-3">
            <div className="text-xs italic px-2 py-1 rounded bg-amber-50 dark:bg-amber-950/30 border-l-2 border-amber-400 text-amber-800 dark:text-amber-200 line-clamp-2">
                &ldquo;{anchorText}&rdquo;
            </div>
            <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Add your comment..."
                className="min-h-[80px] text-sm resize-none"
                autoFocus
                onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault()
                        onSubmit(content)
                    } else if (e.key === "Escape") {
                        onCancel()
                    }
                }}
            />
            <div className="flex items-center gap-2 justify-end">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onCancel}
                    className="h-7 px-2 text-xs"
                >
                    <XIcon className="size-3 mr-1" />
                    Cancel
                </Button>
                <Button
                    size="sm"
                    onClick={() => onSubmit(content)}
                    disabled={!content.trim() || isSubmitting}
                    className="h-7 px-2 text-xs"
                >
                    {isSubmitting ? (
                        <Loader2Icon className="size-3 mr-1 animate-spin" />
                    ) : (
                        <SendIcon className="size-3 mr-1" />
                    )}
                    Comment
                </Button>
            </div>
        </div>
    )
}
