"use client"

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Button } from '@/components/ui/button'
import { Toggle } from '@/components/ui/toggle'
import {
    BoldIcon,
    ItalicIcon,
    ListIcon,
    ListOrderedIcon,
    Undo2Icon,
    Redo2Icon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface RichTextEditorProps {
    content?: string
    placeholder?: string
    onChange?: (html: string) => void
    onSubmit?: (html: string) => void
    submitLabel?: string
    isSubmitting?: boolean
    className?: string
}

export function RichTextEditor({
    content = '',
    placeholder = 'Write something...',
    onChange,
    onSubmit,
    submitLabel = 'Submit',
    isSubmitting = false,
    className,
}: RichTextEditorProps) {
    const editor = useEditor({
        extensions: [
            StarterKit.configure({
                heading: false, // Disable headings for notes
            }),
            Placeholder.configure({
                placeholder,
            }),
        ],
        content,
        editorProps: {
            attributes: {
                class: 'prose prose-sm max-w-none focus:outline-none min-h-[80px] px-3 py-2',
            },
        },
        onUpdate: ({ editor }) => {
            onChange?.(editor.getHTML())
        },
    })

    const handleSubmit = () => {
        if (!editor) return
        const html = editor.getHTML()
        // Don't submit empty content
        if (html === '<p></p>' || !html.trim()) return
        onSubmit?.(html)
        editor.commands.clearContent()
    }

    if (!editor) return null

    return (
        <div className={cn("border rounded-md", className)}>
            {/* Toolbar */}
            <div className="flex items-center gap-1 border-b px-2 py-1.5 bg-muted/30">
                <Toggle
                    size="sm"
                    pressed={editor.isActive('bold')}
                    onPressedChange={() => editor.chain().focus().toggleBold().run()}
                    aria-label="Bold"
                >
                    <BoldIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={editor.isActive('italic')}
                    onPressedChange={() => editor.chain().focus().toggleItalic().run()}
                    aria-label="Italic"
                >
                    <ItalicIcon className="size-4" />
                </Toggle>
                <div className="w-px h-4 bg-border mx-1" />
                <Toggle
                    size="sm"
                    pressed={editor.isActive('bulletList')}
                    onPressedChange={() => editor.chain().focus().toggleBulletList().run()}
                    aria-label="Bullet List"
                >
                    <ListIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={editor.isActive('orderedList')}
                    onPressedChange={() => editor.chain().focus().toggleOrderedList().run()}
                    aria-label="Ordered List"
                >
                    <ListOrderedIcon className="size-4" />
                </Toggle>
                <div className="w-px h-4 bg-border mx-1" />
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => editor.chain().focus().undo().run()}
                    disabled={!editor.can().undo()}
                    className="size-8 p-0"
                >
                    <Undo2Icon className="size-4" />
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => editor.chain().focus().redo().run()}
                    disabled={!editor.can().redo()}
                    className="size-8 p-0"
                >
                    <Redo2Icon className="size-4" />
                </Button>

                {onSubmit && (
                    <Button
                        size="sm"
                        onClick={handleSubmit}
                        disabled={isSubmitting}
                        className="ml-auto"
                    >
                        {isSubmitting ? 'Submitting...' : submitLabel}
                    </Button>
                )}
            </div>

            {/* Editor Content */}
            <EditorContent editor={editor} />
        </div>
    )
}

// CSS for the editor placeholder
const styles = `
.tiptap p.is-editor-empty:first-child::before {
    color: hsl(var(--muted-foreground));
    content: attr(data-placeholder);
    float: left;
    height: 0;
    pointer-events: none;
}
`

// Inject styles
if (typeof document !== 'undefined') {
    const styleElement = document.createElement('style')
    styleElement.textContent = styles
    document.head.appendChild(styleElement)
}
