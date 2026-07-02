"use client"

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
        <div className="flex items-center gap-1 border-b bg-muted/30 px-2 py-1.5">
            <Toggle
                size="sm"
                pressed={editor.isActive("bold")}
                onPressedChange={() => editor.chain().focus().toggleBold().run()}
                aria-label="Bold"
            >
                <BoldIcon className="size-4" />
            </Toggle>
            <Toggle
                size="sm"
                pressed={editor.isActive("italic")}
                onPressedChange={() => editor.chain().focus().toggleItalic().run()}
                aria-label="Italic"
            >
                <ItalicIcon className="size-4" />
            </Toggle>
            <Toggle
                size="sm"
                pressed={editor.isActive("underline")}
                onPressedChange={() => editor.chain().focus().toggleUnderline().run()}
                aria-label="Underline"
            >
                <UnderlineIcon className="size-4" />
            </Toggle>
            <div className="mx-1 h-4 w-px bg-border" />
            <Toggle
                size="sm"
                pressed={editor.isActive("bulletList")}
                onPressedChange={() => editor.chain().focus().toggleBulletList().run()}
                aria-label="Bullet List"
            >
                <ListIcon className="size-4" />
            </Toggle>
            <Toggle
                size="sm"
                pressed={editor.isActive("orderedList")}
                onPressedChange={() => editor.chain().focus().toggleOrderedList().run()}
                aria-label="Ordered List"
            >
                <ListOrderedIcon className="size-4" />
            </Toggle>
            <div className="mx-1 h-4 w-px bg-border" />
            <Toggle
                size="sm"
                pressed={editor.isActive("link")}
                onPressedChange={addLink}
                aria-label="Add Link"
            >
                <LinkIcon className="size-4" />
            </Toggle>
            {enableImages && (
                <Toggle
                    size="sm"
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
            <div className="mx-1 h-4 w-px bg-border" />
            <Toggle
                size="sm"
                pressed={editor.isActive({ textAlign: "left" })}
                onPressedChange={() => editor.chain().focus().setTextAlign("left").run()}
                aria-label="Align Left"
            >
                <AlignLeftIcon className="size-4" />
            </Toggle>
            <Toggle
                size="sm"
                pressed={editor.isActive({ textAlign: "center" })}
                onPressedChange={() => editor.chain().focus().setTextAlign("center").run()}
                aria-label="Align Center"
            >
                <AlignCenterIcon className="size-4" />
            </Toggle>
            <Toggle
                size="sm"
                pressed={editor.isActive({ textAlign: "right" })}
                onPressedChange={() => editor.chain().focus().setTextAlign("right").run()}
                aria-label="Align Right"
            >
                <AlignRightIcon className="size-4" />
            </Toggle>
            <div className="mx-1 h-4 w-px bg-border" />
            <Button
                variant="ghost"
                size="sm"
                onClick={() => editor.chain().focus().undo().run()}
                disabled={!editor.can().undo()}
                className="size-8 p-0"
                aria-label="Undo"
            >
                <Undo2Icon className="size-4" aria-hidden="true" />
            </Button>
            <Button
                variant="ghost"
                size="sm"
                onClick={() => editor.chain().focus().redo().run()}
                disabled={!editor.can().redo()}
                className="size-8 p-0"
                aria-label="Redo"
            >
                <Redo2Icon className="size-4" aria-hidden="true" />
            </Button>

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
    )
}
