"use client"

import "@react-email/editor/themes/default.css"
import "./email-design.css"

import {
    forwardRef,
    useEffect,
    useImperativeHandle,
    useMemo,
    useRef,
    useState,
    type ComponentType,
    type ReactNode,
} from "react"
import { EditorContent, EditorContext, useEditor, type Editor, type JSONContent } from "@tiptap/react"
import { NodeSelection } from "@tiptap/pm/state"
import { useEditorImage } from "@react-email/editor/plugins"
import {
    BubbleMenu,
    BULLET_LIST,
    BUTTON,
    defaultSlashCommands,
    DIVIDER,
    H2,
    Inspector,
    QUOTE,
    SECTION,
    SlashCommand,
    TEXT,
    TWO_COLUMNS,
    type SlashCommandItem,
} from "@react-email/editor/ui"
import {
    CodeIcon,
    Columns2Icon,
    Heading2Icon,
    ImageIcon,
    ListIcon,
    MinusIcon,
    MousePointerClickIcon,
    QuoteIcon,
    SquareIcon,
    TypeIcon,
    type LucideProps,
} from "lucide-react"

import { compileEmailDesign, convertHtmlToDesign, type ConvertedEmailHtml } from "@/components/email/design/compile"
import { EmailHtmlFrame } from "@/components/email/design/email-html-frame"
import { createEmailDesignExtensions } from "@/components/email/design/extensions"
import type { HtmlBlockTarget } from "@/components/email/design/html-block"
import { TemplateVariableList } from "@/components/email/TemplateVariablePicker"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { HTML_BLOCK_NODE, initialEmailDesign, type EmailBodyValue } from "@/lib/email-design"
import type { TemplateVariableRead } from "@/lib/types/template-variable"
import { cn } from "@/lib/utils"

export type EmailDesignEditorHandle = {
    insertText: (text: string) => void
    insertImage: (src: string, alt: string) => void
}

type EmailDesignEditorProps = {
    initialValue: EmailBodyValue
    onChange: (value: EmailBodyValue) => void
    variables: TemplateVariableRead[]
    /** Routes a picked variable; defaults to inserting it into the body. */
    onSelectVariable?: (variable: TemplateVariableRead) => void
    onFocus?: () => void
    /** Fields shown above the email sheet. */
    fields?: ReactNode
    /** Shown in the inspector column under the document styles. */
    settings?: ReactNode
    invalid?: boolean
    error?: ReactNode
    className?: string
}

type HtmlDialogState = { pos: number | null; html: string }

type RailBlock = {
    label: string
    icon: ComponentType<LucideProps>
    item?: SlashCommandItem
    action?: "image" | "html"
}

const RAIL_BLOCKS: RailBlock[] = [
    { label: "Text", icon: TypeIcon, item: TEXT },
    { label: "Heading", icon: Heading2Icon, item: H2 },
    { label: "Button", icon: MousePointerClickIcon, item: BUTTON },
    { label: "Image", icon: ImageIcon, action: "image" },
    { label: "Divider", icon: MinusIcon, item: DIVIDER },
    { label: "Section", icon: SquareIcon, item: SECTION },
    { label: "Columns", icon: Columns2Icon, item: TWO_COLUMNS },
    { label: "List", icon: ListIcon, item: BULLET_LIST },
    { label: "Quote", icon: QuoteIcon, item: QUOTE },
    { label: "HTML", icon: CodeIcon, action: "html" },
]

function rejectImageUpload(): Promise<{ url: string }> {
    return Promise.reject(new Error("Image upload is not available. Insert the image by URL."))
}

/** Opens an empty line after the current block and puts the cursor there. */
function openLineAfterSelection(editor: Editor) {
    const { selection } = editor.state
    if (selection instanceof NodeSelection) {
        editor.chain().focus().insertContentAt(selection.to, { type: "paragraph" }).run()
        return
    }
    const { $from } = selection
    if ($from.parent.type.name === "paragraph" && $from.parent.content.size === 0) {
        editor.commands.focus()
        return
    }
    const after = $from.after($from.depth)
    editor.chain().focus().insertContentAt(after, { type: "paragraph" }).setTextSelection(after + 1).run()
}

function insertBlocksAfterSelection(editor: Editor, content: JSONContent | JSONContent[]) {
    openLineAfterSelection(editor)
    const { from, to } = editor.state.selection
    editor.chain().focus().insertContentAt({ from: from - 1, to: to + 1 }, content).run()
}

function insertTextAtSelection(editor: Editor, text: string) {
    const { selection } = editor.state
    if (selection instanceof NodeSelection) {
        editor.chain().focus().insertContentAt(selection.to, { type: "paragraph", content: [{ type: "text", text }] }).run()
        return
    }
    editor.chain().focus().insertContent(text).run()
}

export const EmailDesignEditor = forwardRef<EmailDesignEditorHandle, EmailDesignEditorProps>(
    function EmailDesignEditor(
        { initialValue, onChange, variables, onSelectVariable, onFocus, fields, settings, invalid, error, className },
        ref,
    ) {
        const [htmlDialog, setHtmlDialog] = useState<HtmlDialogState | null>(null)
        const [convertTarget, setConvertTarget] = useState<HtmlBlockTarget | null>(null)
        const [imageOpen, setImageOpen] = useState(false)
        const onChangeRef = useRef(onChange)
        const onFocusRef = useRef(onFocus)
        const initialValueRef = useRef(initialValue)
        const baselineRef = useRef<string | null>(null)
        const compileSequenceRef = useRef(0)

        useEffect(() => {
            onChangeRef.current = onChange
            onFocusRef.current = onFocus
        })

        const imageExtension = useEditorImage({ uploadImage: rejectImageUpload })
        const extensions = useMemo(
            () => [
                ...createEmailDesignExtensions({
                    onEdit: (target) => setHtmlDialog(target),
                    onConvert: (target) => setConvertTarget(target),
                }),
                imageExtension,
            ],
            [imageExtension],
        )
        const slashItems = useMemo<SlashCommandItem[]>(
            () => [
                ...defaultSlashCommands,
                {
                    title: "HTML",
                    description: "Raw email HTML",
                    icon: <CodeIcon className="size-5" aria-hidden="true" />,
                    category: "Layout",
                    searchTerms: ["html", "code", "raw", "custom"],
                    command: ({ editor, range }) => {
                        editor.chain().focus().deleteRange(range).run()
                        setHtmlDialog({ pos: null, html: "" })
                    },
                },
            ],
            [],
        )

        const emitChange = async (editor: Editor) => {
            const sequence = ++compileSequenceRef.current
            if (JSON.stringify(editor.getJSON()) === baselineRef.current) {
                onChangeRef.current(initialValueRef.current)
                return
            }
            const value = await compileEmailDesign(editor)
            if (sequence !== compileSequenceRef.current || editor.isDestroyed) return
            onChangeRef.current(value)
        }

        const editor = useEditor(
            {
                extensions,
                content: initialEmailDesign(initialValue) as JSONContent,
                immediatelyRender: false,
                editorProps: {
                    attributes: {
                        role: "textbox",
                        "aria-multiline": "true",
                        "aria-label": "Email body",
                        ...(invalid ? { "aria-invalid": "true" } : {}),
                    },
                },
                onCreate: ({ editor: created }) => {
                    baselineRef.current = JSON.stringify(created.getJSON())
                },
                onUpdate: ({ editor: updated }) => {
                    void emitChange(updated)
                },
                onFocus: () => onFocusRef.current?.(),
            },
            [extensions],
        )

        useImperativeHandle(
            ref,
            () => ({
                insertText: (text: string) => {
                    if (editor) insertTextAtSelection(editor, text)
                },
                insertImage: (src: string, alt: string) => {
                    if (!editor) return
                    openLineAfterSelection(editor)
                    editor.chain().focus().setImage({ src, alt }).run()
                },
            }),
            [editor],
        )

        const handleRailBlock = (block: RailBlock) => {
            if (!editor) return
            if (block.action === "image") {
                setImageOpen(true)
                return
            }
            if (block.action === "html") {
                setHtmlDialog({ pos: null, html: "" })
                return
            }
            if (!block.item) return
            openLineAfterSelection(editor)
            const at = editor.state.selection.from
            block.item.command({ editor, range: { from: at, to: at } })
        }

        const handleSelectVariable = (variable: TemplateVariableRead) => {
            if (onSelectVariable) {
                onSelectVariable(variable)
                return
            }
            if (editor) insertTextAtSelection(editor, `{{${variable.name}}}`)
        }

        const saveHtmlBlock = (html: string) => {
            if (!editor || !htmlDialog) return
            const { pos } = htmlDialog
            if (pos === null) {
                insertBlocksAfterSelection(editor, { type: HTML_BLOCK_NODE, attrs: { html } })
            } else {
                editor
                    .chain()
                    .focus()
                    .command(({ tr }) => {
                        tr.setNodeMarkup(pos, undefined, { html })
                        return true
                    })
                    .run()
            }
            setHtmlDialog(null)
        }

        const applyConversion = (blocks: JSONContent[]) => {
            if (!editor || !convertTarget) return
            const node = editor.state.doc.nodeAt(convertTarget.pos)
            if (node?.type.name === HTML_BLOCK_NODE) {
                editor
                    .chain()
                    .focus()
                    .insertContentAt({ from: convertTarget.pos, to: convertTarget.pos + node.nodeSize }, blocks)
                    .run()
            }
            setConvertTarget(null)
        }

        const insertImage = (src: string, alt: string) => {
            if (!editor) return
            openLineAfterSelection(editor)
            editor.chain().focus().setImage({ src, alt }).run()
            setImageOpen(false)
        }

        return (
            <EditorContext.Provider value={{ editor }}>
                <div
                    className={cn(
                        "flex min-h-0 flex-1 flex-col lg:grid lg:grid-cols-[13rem_minmax(0,1fr)_18rem]",
                        className,
                    )}
                >
                    <aside
                        aria-label="Blocks"
                        className="flex max-h-72 min-h-0 flex-col gap-4 overflow-y-auto border-b border-border bg-card p-3 lg:max-h-none lg:border-r lg:border-b-0"
                    >
                        <section aria-labelledby="email-design-blocks" className="grid gap-0.5">
                            <h2
                                id="email-design-blocks"
                                className="px-2 pb-1 text-xs font-medium text-muted-foreground"
                            >
                                Blocks
                            </h2>
                            <div className="grid grid-cols-2 gap-0.5 lg:grid-cols-1">
                                {RAIL_BLOCKS.map((block) => (
                                    <Button
                                        key={block.label}
                                        type="button"
                                        variant="ghost"
                                        disabled={!editor}
                                        onClick={() => handleRailBlock(block)}
                                        className="h-9 justify-start gap-2.5 px-2 font-normal"
                                    >
                                        <span className="flex size-6 items-center justify-center rounded border border-border text-muted-foreground">
                                            <block.icon className="size-3.5" aria-hidden="true" />
                                        </span>
                                        {block.label}
                                    </Button>
                                ))}
                            </div>
                        </section>
                        <section aria-labelledby="email-design-variables" className="grid min-h-0 gap-1">
                            <h2
                                id="email-design-variables"
                                className="px-2 text-xs font-medium text-muted-foreground"
                            >
                                Variables
                            </h2>
                            <TemplateVariableList variables={variables} onSelect={handleSelectVariable} />
                        </section>
                    </aside>

                    <div className="min-h-0 min-w-0 overflow-y-auto bg-muted/40 px-4 py-6 sm:px-6">
                        <div className="mx-auto flex w-full max-w-[600px] flex-col gap-4">
                            {fields}
                            <div
                                className={cn(
                                    "email-design-sheet rounded-sm border bg-white px-6 py-4 text-black shadow-xs",
                                    invalid ? "border-destructive" : "border-border",
                                )}
                            >
                                <EditorContent editor={editor} />
                            </div>
                            {error}
                        </div>
                    </div>

                    <div className="flex min-h-0 flex-col overflow-y-auto border-t border-border bg-card lg:border-t-0 lg:border-l">
                        {editor ? (
                            <Inspector.Root aria-label="Block properties" className="p-3 text-sm">
                                <Inspector.Breadcrumb />
                                <Inspector.Document />
                                <Inspector.Node />
                                <Inspector.Text />
                            </Inspector.Root>
                        ) : null}
                        {settings ? <div className="border-t border-border p-3">{settings}</div> : null}
                    </div>
                </div>

                {editor ? (
                    <>
                        <BubbleMenu hideWhenActiveNodes={["button", "horizontalRule", HTML_BLOCK_NODE]} hideWhenActiveMarks={["link"]} />
                        <BubbleMenu.LinkDefault />
                        <BubbleMenu.ButtonDefault />
                        <BubbleMenu.ImageDefault />
                        <SlashCommand items={slashItems} />
                    </>
                ) : null}

                <HtmlBlockDialog
                    state={htmlDialog}
                    onOpenChange={(open) => {
                        if (!open) setHtmlDialog(null)
                    }}
                    onSave={saveHtmlBlock}
                />
                <ConvertHtmlDialog
                    target={convertTarget}
                    onOpenChange={(open) => {
                        if (!open) setConvertTarget(null)
                    }}
                    onApply={applyConversion}
                />
                <ImageUrlDialog open={imageOpen} onOpenChange={setImageOpen} onInsert={insertImage} />
            </EditorContext.Provider>
        )
    },
)

function HtmlBlockDialog({
    state,
    onOpenChange,
    onSave,
}: {
    state: HtmlDialogState | null
    onOpenChange: (open: boolean) => void
    onSave: (html: string) => void
}) {
    const [html, setHtml] = useState("")
    const [openFor, setOpenFor] = useState<HtmlDialogState | null>(null)
    if (state !== openFor) {
        setOpenFor(state)
        setHtml(state?.html ?? "")
    }

    return (
        <Dialog open={state !== null} onOpenChange={onOpenChange}>
            <DialogContent size="3xl">
                <DialogHeader>
                    <DialogTitle>{state?.pos === null ? "Add HTML" : "Edit HTML"}</DialogTitle>
                </DialogHeader>
                <div className="grid gap-3 lg:grid-cols-2">
                    <Textarea
                        aria-label="HTML"
                        value={html}
                        onChange={(event) => setHtml(event.target.value)}
                        className="min-h-80 resize-y font-mono text-xs leading-relaxed"
                        spellCheck={false}
                    />
                    <div className="max-h-[28rem] overflow-y-auto rounded-md border border-border">
                        <EmailHtmlFrame html={html} title="HTML preview" autoHeight />
                    </div>
                </div>
                <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button type="button" onClick={() => onSave(html)} disabled={!html.trim()}>
                        {state?.pos === null ? "Add" : "Apply"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

type ConversionState =
    | { status: "loading" }
    | { status: "ready"; result: ConvertedEmailHtml }
    | { status: "error" }

type ConversionResult = { target: HtmlBlockTarget } & ConversionState

function ConvertHtmlDialog({
    target,
    onOpenChange,
    onApply,
}: {
    target: HtmlBlockTarget | null
    onOpenChange: (open: boolean) => void
    onApply: (blocks: JSONContent[]) => void
}) {
    const [result, setResult] = useState<ConversionResult | null>(null)
    const conversion: ConversionState =
        result && result.target === target ? result : { status: "loading" }

    useEffect(() => {
        if (!target) return
        let cancelled = false
        convertHtmlToDesign(target.html).then(
            (converted) => {
                if (!cancelled) setResult({ target, status: "ready", result: converted })
            },
            () => {
                if (!cancelled) setResult({ target, status: "error" })
            },
        )
        return () => {
            cancelled = true
        }
    }, [target])

    return (
        <Dialog open={target !== null} onOpenChange={onOpenChange}>
            <DialogContent size="5xl">
                <DialogHeader>
                    <DialogTitle>Convert to blocks</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4 md:grid-cols-2">
                    <section aria-labelledby="convert-original" className="grid gap-2">
                        <h3 id="convert-original" className="text-sm font-medium">
                            Original
                        </h3>
                        <div className="max-h-[60vh] overflow-y-auto rounded-md border border-border">
                            <EmailHtmlFrame html={target?.html ?? ""} title="Original HTML" autoHeight />
                        </div>
                    </section>
                    <section aria-labelledby="convert-blocks" className="grid gap-2">
                        <h3 id="convert-blocks" className="text-sm font-medium">
                            Blocks
                        </h3>
                        <div className="max-h-[60vh] overflow-y-auto rounded-md border border-border">
                            {conversion.status === "ready" ? (
                                <EmailHtmlFrame html={conversion.result.body} title="Converted blocks" autoHeight />
                            ) : conversion.status === "error" ? (
                                <p role="alert" className="p-4 text-sm text-destructive">
                                    This HTML could not be converted. Keep it as an HTML block.
                                </p>
                            ) : (
                                <p className="p-4 text-sm text-muted-foreground">Converting…</p>
                            )}
                        </div>
                    </section>
                </div>
                <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                        Keep HTML
                    </Button>
                    <Button
                        type="button"
                        disabled={conversion.status !== "ready"}
                        onClick={() => {
                            if (conversion.status === "ready") onApply(conversion.result.blocks)
                        }}
                    >
                        Use blocks
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

function ImageUrlDialog({
    open,
    onOpenChange,
    onInsert,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    onInsert: (src: string, alt: string) => void
}) {
    const [src, setSrc] = useState("")
    const [alt, setAlt] = useState("")
    const isHttps = /^https:\/\/\S+$/i.test(src.trim())

    return (
        <Dialog
            open={open}
            onOpenChange={(next) => {
                if (!next) {
                    setSrc("")
                    setAlt("")
                }
                onOpenChange(next)
            }}
        >
            <DialogContent size="md">
                <DialogHeader>
                    <DialogTitle>Add image</DialogTitle>
                </DialogHeader>
                <form
                    className="grid gap-4"
                    onSubmit={(event) => {
                        event.preventDefault()
                        if (isHttps) onInsert(src.trim(), alt.trim())
                    }}
                >
                    <div className="grid gap-2">
                        <Label htmlFor="email-image-url">Image URL</Label>
                        <Input
                            id="email-image-url"
                            type="url"
                            inputMode="url"
                            placeholder="https://"
                            value={src}
                            onChange={(event) => setSrc(event.target.value)}
                            aria-invalid={src && !isHttps ? true : undefined}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="email-image-alt">Alt text</Label>
                        <Input id="email-image-alt" value={alt} onChange={(event) => setAlt(event.target.value)} />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={!isHttps}>
                            Add image
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
