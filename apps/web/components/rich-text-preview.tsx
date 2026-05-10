"use client"

import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
import { sanitizeHtml } from "@/lib/utils/sanitize"
import { cn } from "@/lib/utils"

type RichTextPreviewProps = {
    html: string
    className?: string
}

export function RichTextPreview({ html, className }: RichTextPreviewProps) {
    const sanitizedHtml = sanitizeHtml(html)

    return (
        <TrustedSanitizedHtmlContent
            html={sanitizedHtml}
            className={cn("prose prose-sm max-w-none focus:outline-none dark:prose-invert", className)}
        />
    )
}
