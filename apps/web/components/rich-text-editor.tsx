"use client"

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Image from '@tiptap/extension-image'
import { cn } from '@/lib/utils'
import { useEffect, useImperativeHandle, useState, type Ref } from 'react'
import { RichTextEditorLoading } from '@/components/rich-text-editor-loading'
import { RichTextEditorToolbar } from '@/components/rich-text-editor-toolbar'

interface RichTextEditorProps {
    ref?: Ref<RichTextEditorHandle>
    content?: string
    placeholder?: string
    onChange?: (html: string) => void
    onFocus?: () => void
    onSubmit?: (html: string) => void
    submitLabel?: string
    isSubmitting?: boolean
    className?: string
    minHeight?: string
    maxHeight?: string
    enableImages?: boolean
    enableEmojiPicker?: boolean
    ariaLabel?: string
    ariaLabelledBy?: string
}

export type RichTextEditorHandle = {
    insertText: (text: string) => void
    insertHtml: (html: string) => void
}

export function RichTextEditor({
    ref,
    content = '',
    placeholder = 'Write something...',
    onChange,
    onFocus,
    onSubmit,
    submitLabel = 'Submit',
    isSubmitting = false,
    className,
    minHeight = '80px',
    maxHeight = '300px',
    enableImages = false,
    enableEmojiPicker = false,
    ariaLabel,
    ariaLabelledBy,
}: RichTextEditorProps) {
    const [emojiOpen, setEmojiOpen] = useState(false)

    const editor = useEditor({
        immediatelyRender: false, // Fix SSR hydration mismatch
        shouldRerenderOnTransaction: false, // Better performance with React 19
        extensions: [
            StarterKit.configure({
                heading: false, // Disable headings for notes
                link: {
                    openOnClick: false,
                    HTMLAttributes: {
                        class: 'text-primary underline cursor-pointer',
                    },
                },
            }),
            Placeholder.configure({
                placeholder,
            }),
            TextAlign.configure({
                types: ['paragraph'],
            }),
            ...(enableImages
                ? [
                      Image.configure({
                          allowBase64: false,
                          HTMLAttributes: {
                              style: 'max-width: 180px; height: auto; display: block;',
                          },
                      }),
                  ]
                : []),
        ],
        content,
        editorProps: {
            attributes: {
                class: `prose prose-sm max-w-none focus:outline-none min-h-[${minHeight}] px-3 py-2`,
            },
        },
        onUpdate: ({ editor }) => {
            onChange?.(editor.getHTML())
        },
    })

    useImperativeHandle(
        ref,
        () => ({
            insertText: (text: string) => {
                if (!editor) return
                editor.chain().focus().insertContent(text).run()
            },
            insertHtml: (html: string) => {
                if (!editor) return
                editor.chain().focus().insertContent(html).run()
            },
        }),
        [editor]
    )

    // Sync content when it changes externally
    useEffect(() => {
        if (editor && content !== editor.getHTML()) {
            editor.commands.setContent(content)
        }
    }, [content, editor])

    const handleSubmit = () => {
        if (!editor) return
        const html = editor.getHTML()
        // Don't submit empty content
        if (html === '<p></p>' || !html.trim()) return
        onSubmit?.(html)
        editor.commands.clearContent()
    }

    const handleEmojiOpenChange = (open: boolean) => {
        setEmojiOpen(open)
    }

    const insertEmoji = (emoji: string) => {
        if (!editor) return
        editor.chain().focus().insertContent(emoji).run()
        setEmojiOpen(false)
    }

    if (!editor) {
        return (
            <RichTextEditorLoading
                className={className}
                minHeight={minHeight}
                showSubmit={Boolean(onSubmit)}
            />
        )
    }

    return (
        <div className={cn("border rounded-md", className)}>
            <RichTextEditorToolbar
                editor={editor}
                enableImages={enableImages}
                enableEmojiPicker={enableEmojiPicker}
                emojiOpen={emojiOpen}
                onEmojiOpenChange={handleEmojiOpenChange}
                onInsertEmoji={insertEmoji}
                onSubmit={onSubmit ? handleSubmit : undefined}
                submitLabel={submitLabel}
                isSubmitting={isSubmitting}
            />

            <div className="overflow-y-auto" style={{ maxHeight }} onFocusCapture={() => onFocus?.()}>
                <EditorContent
                    editor={editor}
                    aria-label={ariaLabel}
                    aria-labelledby={ariaLabelledBy}
                />
            </div>
        </div>
    )
}
