"use client"

import {
    AlignCenterIcon,
    AlignLeftIcon,
    AlignRightIcon,
    BoldIcon,
    ItalicIcon,
    ListIcon,
    ListOrderedIcon,
    Redo2Icon,
    UnderlineIcon,
    Undo2Icon,
} from "lucide-react"
import {
    useImperativeHandle,
    useRef,
    type ClipboardEventHandler,
    type DragEventHandler,
    type FocusEventHandler,
    type MouseEventHandler,
    type Ref,
} from "react"

import { TrustedSanitizedHtmlFragment } from "@/components/safe-html-content"
import { Button } from "@/components/ui/button"
import { normalizeTemplateHtml } from "@/lib/email-template-html"
import { sanitizeEmailTemplatePreviewHtml } from "@/lib/email-template-preview"
import { cn } from "@/lib/utils"

type EmailTemplateVisualEditorProps = {
    ref?: Ref<EmailTemplateVisualEditorHandle>
    content: string
    onChange: (html: string) => void
    onFocus?: FocusEventHandler<HTMLDivElement>
    ariaLabel?: string
    ariaLabelledBy?: string
    className?: string
    minHeight?: string
    maxHeight?: string
}

export type EmailTemplateVisualEditorHandle = {
    getHtml: () => string
    insertText: (text: string) => void
}

const TEMPLATE_ATTRIBUTE_RE = /\b(href|src)\s*=\s*(["'])([^"']*\{\{\s*[a-zA-Z0-9_]+\s*\}\}[^"']*)\2/gi
const EXACT_TEMPLATE_TOKEN_RE = /^\{\{\s*[a-zA-Z0-9_]+\s*\}\}$/
const SAFE_TEMPLATE_URL_RE = /^(?:https?:\/\/|mailto:|tel:|\/|#)/i

function sanitizeAuthoringHtml(html: string): string {
    const protectedAttributes: Array<{ placeholder: string; value: string }> = []
    const protectedHtml = html.replace(
        TEMPLATE_ATTRIBUTE_RE,
        (attribute, name: string, quote: string, value: string) => {
            if (
                !EXACT_TEMPLATE_TOKEN_RE.test(value.trim()) &&
                !SAFE_TEMPLATE_URL_RE.test(value.trim())
            ) {
                return attribute
            }

            const placeholder = `https://template-variable.invalid/${protectedAttributes.length}`
            protectedAttributes.push({ placeholder, value })
            return `${name}=${quote}${placeholder}${quote}`
        },
    )

    let sanitized = sanitizeEmailTemplatePreviewHtml(protectedHtml)
    for (const { placeholder, value } of protectedAttributes) {
        sanitized = sanitized.replaceAll(placeholder, value)
    }
    return sanitized.replace(
        /(<\/?(?:table|thead|tbody|tfoot|tr|colgroup|col)\b[^>]*>)\s+(?=<\/?(?:table|thead|tbody|tfoot|tr|td|th|colgroup|col)\b)/gi,
        "$1",
    )
}

type EditorCommand =
    | "bold"
    | "italic"
    | "underline"
    | "insertUnorderedList"
    | "insertOrderedList"
    | "justifyLeft"
    | "justifyCenter"
    | "justifyRight"
    | "undo"
    | "redo"

type ToolbarAction = {
    command: EditorCommand
    label: string
    icon: typeof BoldIcon
}

const TOOLBAR_ACTIONS: ToolbarAction[] = [
    { command: "bold", label: "Bold", icon: BoldIcon },
    { command: "italic", label: "Italic", icon: ItalicIcon },
    { command: "underline", label: "Underline", icon: UnderlineIcon },
    { command: "insertUnorderedList", label: "Bullet list", icon: ListIcon },
    { command: "insertOrderedList", label: "Numbered list", icon: ListOrderedIcon },
    { command: "justifyLeft", label: "Align left", icon: AlignLeftIcon },
    { command: "justifyCenter", label: "Align center", icon: AlignCenterIcon },
    { command: "justifyRight", label: "Align right", icon: AlignRightIcon },
    { command: "undo", label: "Undo", icon: Undo2Icon },
    { command: "redo", label: "Redo", icon: Redo2Icon },
]

export function EmailTemplateVisualEditor({
    ref,
    content,
    onChange,
    onFocus,
    ariaLabel,
    ariaLabelledBy,
    className,
    minHeight = "320px",
    maxHeight = "560px",
}: EmailTemplateVisualEditorProps) {
    const editorRef = useRef<HTMLDivElement | null>(null)
    const initialVisualBodyRef = useRef(sanitizeAuthoringHtml(content))
    const currentVisualBodyRef = useRef(initialVisualBodyRef.current)
    const currentHtmlRef = useRef(content)

    const commitEditorHtml = () => {
        const editor = editorRef.current
        if (!editor) return currentHtmlRef.current

        const sanitizedBody = sanitizeAuthoringHtml(editor.innerHTML)
        if (editor.innerHTML !== sanitizedBody) {
            editor.innerHTML = sanitizedBody
        }
        if (sanitizedBody === currentVisualBodyRef.current) {
            return currentHtmlRef.current
        }

        currentVisualBodyRef.current = sanitizedBody
        const nextHtml = normalizeTemplateHtml(sanitizedBody)
        currentHtmlRef.current = nextHtml
        onChange(nextHtml)
        return nextHtml
    }

    const runCommand = (command: EditorCommand) => {
        const editor = editorRef.current
        if (!editor) return
        const before = editor.innerHTML
        editor.focus()
        editor.ownerDocument.execCommand?.(command)
        if (editor.innerHTML !== before) commitEditorHtml()
    }

    const insertContent = (value: string, asHtml: boolean) => {
        const editor = editorRef.current
        if (!editor) return
        const before = editor.innerHTML
        const insertValue = asHtml ? sanitizeAuthoringHtml(value) : value
        editor.focus()
        editor.ownerDocument.execCommand?.(
            asHtml ? "insertHTML" : "insertText",
            false,
            insertValue,
        )
        if (editor.innerHTML !== before) commitEditorHtml()
    }

    useImperativeHandle(
        ref,
        () => ({
            getHtml: () => currentHtmlRef.current,
            insertText: (text: string) => insertContent(text, false),
        }),
    )

    const handlePaste: ClipboardEventHandler<HTMLDivElement> = (event) => {
        event.preventDefault()
        const html = event.clipboardData.getData("text/html")
        insertContent(
            html || event.clipboardData.getData("text/plain"),
            Boolean(html),
        )
    }

    const handleDrop: DragEventHandler<HTMLDivElement> = (event) => {
        event.preventDefault()
        const html = event.dataTransfer.getData("text/html")
        insertContent(
            html || event.dataTransfer.getData("text/plain"),
            Boolean(html),
        )
    }

    const preserveSelection: MouseEventHandler<HTMLButtonElement> = (event) => {
        event.preventDefault()
    }

    return (
        <div className={cn("overflow-hidden rounded-md border", className)}>
            <div
                role="toolbar"
                aria-label="Email formatting"
                className="flex flex-wrap items-center gap-1 border-b bg-muted/30 p-2"
            >
                {TOOLBAR_ACTIONS.map(({ command, label, icon: Icon }) => (
                    <Button
                        key={command}
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label={label}
                        title={label}
                        onMouseDown={preserveSelection}
                        onClick={() => runCommand(command)}
                    >
                        <Icon className="size-4" />
                    </Button>
                ))}
            </div>
            <div
                ref={editorRef}
                role="textbox"
                aria-label={ariaLabel}
                aria-labelledby={ariaLabelledBy}
                aria-multiline="true"
                contentEditable
                suppressContentEditableWarning
                onFocus={onFocus}
                onInput={commitEditorHtml}
                onPaste={handlePaste}
                onDrop={handleDrop}
                onClickCapture={(event) => {
                    if ((event.target as Element).closest("a")) {
                        event.preventDefault()
                    }
                }}
                className="prose prose-sm max-w-none overflow-y-auto bg-white px-4 py-3 text-stone-900 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 [&_img]:max-w-full [&_p]:whitespace-pre-wrap"
                style={{ minHeight, maxHeight }}
            >
                <TrustedSanitizedHtmlFragment html={initialVisualBodyRef.current} />
            </div>
            <p className="border-t bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                Stored layout, tables, images, and variables are preserved. Use
                HTML source for structural changes.
            </p>
        </div>
    )
}
