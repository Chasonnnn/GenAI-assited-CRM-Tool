"use client"

import { CopyButton } from "@/components/ui/copy-button"

export function EmailHtmlSource({ html }: { html: string }) {
    return (
        <section aria-labelledby="email-html-source-heading" className="mx-auto grid max-w-4xl gap-2">
            <div className="flex items-center justify-between gap-3">
                <h2 id="email-html-source-heading" className="text-sm font-medium">
                    Email HTML
                </h2>
                <CopyButton value={html} variant="outline" size="sm">
                    Copy HTML
                </CopyButton>
            </div>
            <pre className="overflow-x-auto rounded-md border border-border bg-card p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">
                {html}
            </pre>
        </section>
    )
}
