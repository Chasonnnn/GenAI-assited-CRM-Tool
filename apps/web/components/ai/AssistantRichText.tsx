"use client"

import * as React from "react"
import MarkdownIt from "markdown-it"

import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
import { sanitizeHtml } from "@/lib/utils/sanitize"
import { cn } from "@/lib/utils"

const markdown = new MarkdownIt({
    breaks: true,
    html: false,
    linkify: true,
})

const defaultLinkOpenRenderer =
    markdown.renderer.rules.link_open ??
    ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))

markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
    const token = tokens[index]
    if (!token) {
        return defaultLinkOpenRenderer(tokens, index, options, env, self)
    }
    token.attrSet("target", "_blank")
    token.attrSet("rel", "noopener noreferrer")
    return defaultLinkOpenRenderer(tokens, index, options, env, self)
}

type AssistantRichTextProps = {
    content: string
    className?: string
}

function useHasMounted() {
    return React.useSyncExternalStore(
        () => () => undefined,
        () => true,
        () => false,
    )
}

export function AssistantRichText({ content, className }: AssistantRichTextProps) {
    const hasMounted = useHasMounted()
    const markdownHtml = markdown.render(content)
    const html = hasMounted ? sanitizeHtml(markdownHtml) : markdownHtml

    return (
        <TrustedSanitizedHtmlContent
            html={html}
            className={cn(
                "text-sm leading-relaxed break-words",
                "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
                "[&_p]:my-2 [&_strong]:font-semibold",
                "[&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:text-lg [&_h1]:font-semibold",
                "[&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:text-base [&_h2]:font-semibold",
                "[&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:text-sm [&_h3]:font-semibold",
                "[&_h4]:mt-3 [&_h4]:mb-1.5 [&_h4]:text-sm [&_h4]:font-semibold",
                "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5",
                "[&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5",
                "[&_li]:my-1 [&_li>p]:my-0",
                "[&_a]:font-medium [&_a]:underline [&_a]:underline-offset-2",
                "[&_blockquote]:my-2 [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
                "[&_code]:rounded [&_code]:bg-background/70 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.85em]",
                "[&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-background/70 [&_pre]:p-3",
                "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
                className,
            )}
        />
    )
}
