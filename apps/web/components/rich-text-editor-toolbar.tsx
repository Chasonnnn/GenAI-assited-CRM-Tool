"use client"

import type * as React from "react"
import type { Editor } from "@tiptap/react"
import {
    AlignCenterIcon,
    AlignLeftIcon,
    AlignRightIcon,
    BoldIcon,
    ImageIcon,
    ItalicIcon,
    LinkIcon,
    ListIcon,
    ListOrderedIcon,
    Redo2Icon,
    UnderlineIcon,
    Undo2Icon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Toggle } from "@/components/ui/toggle"
import { RichTextEditorEmojiPopover } from "@/components/rich-text-editor-emoji-popover"

/** Every toolbar control is a 32px square, so toggles and buttons line up on one row. */
const TOOLBAR_ITEM_CLASS = "size-8 min-w-8 p-0"

// Same effect as TextAlign's setTextAlign for the paragraph-only configuration. @react-email/editor
// 1.7.11 declares its own Commands["textAlign"] group, which hides setTextAlign from the types.
function alignParagraph(editor: Editor, alignment: "left" | "center" | "right") {
    editor.chain().focus().updateAttributes("paragraph", { textAlign: alignment }).run()
}

function ToolbarGroup({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div role="group" aria-label={label} className="flex items-center gap-1">
            <div aria-hidden="true" className="mx-1 h-4 w-px shrink-0 bg-border" />
            {children}
        </div>
    )
}

interface RichTextEditorToolbarProps {
    editor: Editor
    enableImages: boolean
    enableEmojiPicker: boolean
    emojiOpen: boolean
    onEmojiOpenChange: (open: boolean) => void
    onInsertEmoji: (emoji: string) => void
    onSubmit: (() => void) | undefined
    submitLabel: string
    isSubmitting: boolean
}

export function RichTextEditorToolbar({
    editor,
    enableImages,
    enableEmojiPicker,
    emojiOpen,
    onEmojiOpenChange,
    onInsertEmoji,
    onSubmit,
    submitLabel,
    isSubmitting,
}: RichTextEditorToolbarProps) {
    const addLink = () => {
        const previousUrl = editor.getAttributes("link").href || ""
        const url = window.prompt("Enter URL:", previousUrl)

        if (url === null) return
        if (url === "") {
            editor.chain().focus().extendMarkRange("link").unsetLink().run()
            return
        }

        editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run()
    }

    const addImage = () => {
        const url = window.prompt("Enter image URL:")
        if (!url) return
        editor.chain().focus().setImage({ src: url.trim(), alt: "Logo" }).run()
    }

    return (
        // Each group starts with its own divider and wraps as a unit. The rows are shifted left by
        // one divider plus its gap (4px margin + 1px + 4px margin + 4px gap = 13px) and clipped, so
        // the divider that starts each row is hidden and no row starts or ends with a divider.
        // The padding keeps focus rings inside the clip box.
        <div className="min-w-0 overflow-hidden border-b bg-muted/30 px-2 py-1.5">
            <div className="-ml-[13px] flex min-w-0 flex-wrap items-center gap-y-1">
                <ToolbarGroup label="Text style">
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive("bold")}
                        onPressedChange={() => editor.chain().focus().toggleBold().run()}
                        aria-label="Bold"
                    >
                        <BoldIcon className="size-4" />
                    </Toggle>
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive("italic")}
                        onPressedChange={() => editor.chain().focus().toggleItalic().run()}
                        aria-label="Italic"
                    >
                        <ItalicIcon className="size-4" />
                    </Toggle>
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive("underline")}
                        onPressedChange={() => editor.chain().focus().toggleUnderline().run()}
                        aria-label="Underline"
                    >
                        <UnderlineIcon className="size-4" />
                    </Toggle>
                </ToolbarGroup>
                <ToolbarGroup label="Lists">
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive("bulletList")}
                        onPressedChange={() => editor.chain().focus().toggleBulletList().run()}
                        aria-label="Bullet List"
                    >
                        <ListIcon className="size-4" />
                    </Toggle>
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive("orderedList")}
                        onPressedChange={() => editor.chain().focus().toggleOrderedList().run()}
                        aria-label="Ordered List"
                    >
                        <ListOrderedIcon className="size-4" />
                    </Toggle>
                </ToolbarGroup>
                <ToolbarGroup label="Insert">
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive("link")}
                        onPressedChange={addLink}
                        aria-label="Add Link"
                    >
                        <LinkIcon className="size-4" />
                    </Toggle>
                    {enableImages && (
                        <Toggle
                            size="sm"
                            className={TOOLBAR_ITEM_CLASS}
                            pressed={false}
                            onPressedChange={addImage}
                            aria-label="Insert Image"
                        >
                            <ImageIcon className="size-4" />
                        </Toggle>
                    )}
                    {enableEmojiPicker && (
                        <RichTextEditorEmojiPopover
                            open={emojiOpen}
                            onOpenChange={onEmojiOpenChange}
                            onSelectEmoji={onInsertEmoji}
                        />
                    )}
                </ToolbarGroup>
                <ToolbarGroup label="Alignment">
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive({ textAlign: "left" })}
                        onPressedChange={() => alignParagraph(editor, "left")}
                        aria-label="Align Left"
                    >
                        <AlignLeftIcon className="size-4" />
                    </Toggle>
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive({ textAlign: "center" })}
                        onPressedChange={() => alignParagraph(editor, "center")}
                        aria-label="Align Center"
                    >
                        <AlignCenterIcon className="size-4" />
                    </Toggle>
                    <Toggle
                        size="sm"
                        className={TOOLBAR_ITEM_CLASS}
                        pressed={editor.isActive({ textAlign: "right" })}
                        onPressedChange={() => alignParagraph(editor, "right")}
                        aria-label="Align Right"
                    >
                        <AlignRightIcon className="size-4" />
                    </Toggle>
                </ToolbarGroup>
                <ToolbarGroup label="History">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => editor.chain().focus().undo().run()}
                        disabled={!editor.can().undo()}
                        className={TOOLBAR_ITEM_CLASS}
                        aria-label="Undo"
                    >
                        <Undo2Icon className="size-4" aria-hidden="true" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => editor.chain().focus().redo().run()}
                        disabled={!editor.can().redo()}
                        className={TOOLBAR_ITEM_CLASS}
                        aria-label="Redo"
                    >
                        <Redo2Icon className="size-4" aria-hidden="true" />
                    </Button>
                </ToolbarGroup>

                {onSubmit && (
                    <Button
                        size="sm"
                        onClick={onSubmit}
                        disabled={isSubmitting}
                        className="ml-auto"
                    >
                        {isSubmitting ? "Submitting..." : submitLabel}
                    </Button>
                )}
            </div>
        </div>
    )
}
