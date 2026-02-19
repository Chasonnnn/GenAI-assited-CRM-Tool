"use client"

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Image from '@tiptap/extension-image'
import EmojiPicker, { EmojiStyle, SuggestionMode, type EmojiClickData } from 'emoji-picker-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Toggle } from '@/components/ui/toggle'
import {
    BoldIcon,
    ItalicIcon,
    UnderlineIcon,
    ListIcon,
    ListOrderedIcon,
    LinkIcon,
    AlignLeftIcon,
    AlignCenterIcon,
    AlignRightIcon,
    ImageIcon,
    Undo2Icon,
    Redo2Icon,
    SmileIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from 'react'

interface RichTextEditorProps {
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

export const RichTextEditor = forwardRef<RichTextEditorHandle, RichTextEditorProps>(function RichTextEditor(
    {
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
    }: RichTextEditorProps,
    ref
) {
    const [mounted, setMounted] = useState(false)
    const [emojiOpen, setEmojiOpen] = useState(false)
    const [suggestedEmojisMode, setSuggestedEmojisMode] = useState<SuggestionMode>(SuggestionMode.FREQUENT)

    useEffect(() => {
        setMounted(true)
    }, [])

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

    const addLink = useCallback(() => {
        if (!editor) return
        const previousUrl = editor.getAttributes('link').href || ''
        const url = window.prompt('Enter URL:', previousUrl)

        if (url === null) return
        if (url === '') {
            editor.chain().focus().extendMarkRange('link').unsetLink().run()
            return
        }

        editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
    }, [editor])

    const addImage = useCallback(() => {
        if (!editor) return
        const url = window.prompt('Enter image URL:')
        if (!url) return
        editor.chain().focus().setImage({ src: url.trim(), alt: 'Logo' }).run()
    }, [editor])

    const insertEmoji = useCallback(
        (emoji: string) => {
            if (!editor) return
            editor.chain().focus().insertContent(emoji).run()
            setEmojiOpen(false)
        },
        [editor]
    )

    const handleEmojiOpenChange = useCallback((open: boolean) => {
        setEmojiOpen(open)
        if (!open) return
        setSuggestedEmojisMode(SuggestionMode.FREQUENT)
    }, [])

    const handleEmojiClick = useCallback(
        (emojiData: EmojiClickData) => {
            insertEmoji(emojiData.emoji)
        },
        [insertEmoji]
    )

    if (!mounted || !editor) {
        // Show placeholder while editor initializes
        return (
            <div className={cn("border rounded-md", className)}>
                <div className="flex items-center gap-1 border-b px-2 py-1.5 bg-muted/30 h-10">
                    <div className="h-6 w-6 rounded bg-muted animate-pulse" />
                    <div className="h-6 w-6 rounded bg-muted animate-pulse" />
                    <div className="h-6 w-6 rounded bg-muted animate-pulse" />
                    {onSubmit && (
                        <div className="ml-auto h-7 w-16 rounded bg-muted animate-pulse" />
                    )}
                </div>
                <div className="px-3 py-2" style={{ minHeight }}>
                    <div className="h-4 w-3/4 rounded bg-muted/50 animate-pulse" />
                </div>
            </div>
        )
    }

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
                <Toggle
                    size="sm"
                    pressed={editor.isActive('underline')}
                    onPressedChange={() => editor.chain().focus().toggleUnderline().run()}
                    aria-label="Underline"
                >
                    <UnderlineIcon className="size-4" />
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
                <Toggle
                    size="sm"
                    pressed={editor.isActive('link')}
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
                    <Popover open={emojiOpen} onOpenChange={handleEmojiOpenChange}>
                        <PopoverTrigger
                            render={
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="size-8 p-0"
                                    aria-label="Insert Emoji"
                                >
                                    <SmileIcon className="size-4" />
                                </Button>
                            }
                        />
                        <PopoverContent className="w-[27rem] p-2" align="start">
                            <div className="space-y-2">
                                <div className="flex items-center justify-between px-1">
                                    <span className="text-xs font-medium text-muted-foreground">Suggested</span>
                                    <div className="flex items-center gap-1">
                                        <Button
                                            type="button"
                                            variant={suggestedEmojisMode === SuggestionMode.FREQUENT ? 'default' : 'ghost'}
                                            size="sm"
                                            className="h-7 px-2 text-xs"
                                            onClick={() => setSuggestedEmojisMode(SuggestionMode.FREQUENT)}
                                        >
                                            Frequent
                                        </Button>
                                        <Button
                                            type="button"
                                            variant={suggestedEmojisMode === SuggestionMode.RECENT ? 'default' : 'ghost'}
                                            size="sm"
                                            className="h-7 px-2 text-xs"
                                            onClick={() => setSuggestedEmojisMode(SuggestionMode.RECENT)}
                                        >
                                            Recent
                                        </Button>
                                    </div>
                                </div>

                                <div data-testid="emoji-picker-root" className="[&_aside.EmojiPickerReact]:!w-full">
                                    <EmojiPicker
                                        onEmojiClick={handleEmojiClick}
                                        suggestedEmojisMode={suggestedEmojisMode}
                                        emojiStyle={EmojiStyle.NATIVE}
                                        searchPlaceholder="Search emojis"
                                        lazyLoadEmojis
                                        width="100%"
                                        height={360}
                                        previewConfig={{ showPreview: false }}
                                    />
                                </div>
                            </div>
                        </PopoverContent>
                    </Popover>
                )}
                <div className="w-px h-4 bg-border mx-1" />
                <Toggle
                    size="sm"
                    pressed={editor.isActive({ textAlign: 'left' })}
                    onPressedChange={() => editor.chain().focus().setTextAlign('left').run()}
                    aria-label="Align Left"
                >
                    <AlignLeftIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={editor.isActive({ textAlign: 'center' })}
                    onPressedChange={() => editor.chain().focus().setTextAlign('center').run()}
                    aria-label="Align Center"
                >
                    <AlignCenterIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={editor.isActive({ textAlign: 'right' })}
                    onPressedChange={() => editor.chain().focus().setTextAlign('right').run()}
                    aria-label="Align Right"
                >
                    <AlignRightIcon className="size-4" />
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

            {/* Editor Content - with scroll support */}
            <div className="overflow-y-auto" style={{ maxHeight }} onFocusCapture={() => onFocus?.()}>
                <EditorContent
                    editor={editor}
                    aria-label={ariaLabel}
                    aria-labelledby={ariaLabelledBy}
                />
            </div>
        </div>
    )
})
