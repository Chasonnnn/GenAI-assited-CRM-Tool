"use client"

import { EditorContent, useEditor } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import TextAlign from "@tiptap/extension-text-align"
import { useEffect, useState } from "react"

import { sanitizeHtml } from "@/lib/utils/sanitize"
import { cn } from "@/lib/utils"

type RichTextPreviewProps = {
    html: string
    className?: string
}

function extractPlainText(html: string): string {
    return html
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<\/p>/gi, "\n")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim()
}

export function RichTextPreview({ html, className }: RichTextPreviewProps) {
    const [mounted, setMounted] = useState(false)
    const sanitizedHtml = sanitizeHtml(html)

    useEffect(() => {
        setMounted(true)
    }, [])

    const editor = useEditor({
        immediatelyRender: false,
        shouldRerenderOnTransaction: false,
        editable: false,
        extensions: [
            StarterKit.configure({
                heading: false,
                link: {
                    openOnClick: true,
                    HTMLAttributes: {
                        class: "text-primary underline",
                        rel: "noopener noreferrer",
                        target: "_blank",
                    },
                },
            }),
            TextAlign.configure({
                types: ["paragraph"],
            }),
        ],
        content: sanitizedHtml,
        editorProps: {
            attributes: {
                class: cn("prose prose-sm max-w-none focus:outline-none dark:prose-invert", className),
            },
        },
    })

    useEffect(() => {
        if (editor && sanitizedHtml !== editor.getHTML()) {
            editor.commands.setContent(sanitizedHtml)
        }
    }, [editor, sanitizedHtml])

    if (!mounted || !editor) {
        return (
            <div className={cn("text-sm whitespace-pre-wrap text-foreground", className)}>
                {extractPlainText(sanitizedHtml)}
            </div>
        )
    }

    return <EditorContent editor={editor} />
}
