"use client"

/**
 * TranscriptEditor - TipTap-based rich text editor for interview transcripts.
 *
 * Features:
 * - Headings (H1, H2, H3)
 * - Bold, Italic, Underline
 * - Bullet and ordered lists
 * - Links
 * - Comment marks for anchored notes
 * - Undo/Redo
 * - Paste handling with format preservation
 * - Returns TipTap JSON (canonical format)
 */

import { useEditor, useEditorState, EditorContent, Mark, mergeAttributes, type JSONContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import { Button } from '@/components/ui/button'
import { Toggle } from '@/components/ui/toggle'
import {
    BoldIcon,
    ItalicIcon,
    UnderlineIcon,
    ListIcon,
    ListOrderedIcon,
    LinkIcon,
    Undo2Icon,
    Redo2Icon,
    Heading1Icon,
    Heading2Icon,
    Heading3Icon,
    MessageSquareIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TipTapDoc } from '@/lib/api/interviews'
import { useSyncTipTapJsonContent } from '@/lib/hooks/use-sync-tiptap-json-content'

const isTipTapDoc = (value: JSONContent): value is TipTapDoc => value?.type === 'doc'

/**
 * Comment mark extension for anchored notes.
 * Stores a stable commentId that links to the note.
 */
const CommentMark = Mark.create({
    name: 'comment',

    addOptions() {
        return {
            HTMLAttributes: {},
        } satisfies { HTMLAttributes: Record<string, unknown> }
    },

    addAttributes() {
        return {
            commentId: {
                default: null,
                parseHTML: (element: HTMLElement) => element.getAttribute('data-comment-id'),
                renderHTML: (attributes: { commentId?: string }) => {
                    if (!attributes.commentId) return {}
                    return { 'data-comment-id': attributes.commentId }
                },
            },
        }
    },

    parseHTML() {
        return [
            {
                tag: 'span[data-comment-id]',
            },
        ]
    },

    renderHTML({ HTMLAttributes }: { HTMLAttributes: Record<string, unknown> }) {
        return [
            'span',
            mergeAttributes(
                this.options.HTMLAttributes,
                HTMLAttributes,
                {
                    class: 'comment-highlight bg-primary/10 border-b-2 border-primary/40 cursor-pointer',
                }
            ),
            0,
        ]
    },
})

interface TranscriptEditorProps {
    /** Initial TipTap JSON content */
    content?: TipTapDoc | null
    /** Placeholder text */
    placeholder?: string
    /** Called on every change with TipTap JSON */
    onChange?: (json: TipTapDoc) => void
    /** Additional class names */
    className?: string
    /** Minimum height for the editor */
    minHeight?: string
    /** Maximum height (enables scrolling) */
    maxHeight?: string
    /** Whether the editor is read-only */
    readOnly?: boolean
    /** Whether to show comment functionality */
    showComments?: boolean
    /** Called when user wants to add a comment to selected text */
    onAddComment?: (selectedText: string, commentId: string) => void
    /** Called when a comment is clicked */
    onCommentClick?: (commentId: string) => void
}

export function TranscriptEditor({
    content,
    placeholder = 'Start typing your transcript or paste content from Word, Google Docs...',
    onChange,
    className,
    minHeight = '200px',
    maxHeight = '500px',
    readOnly = false,
    showComments = false,
    onAddComment,
    onCommentClick,
}: TranscriptEditorProps) {
    const editor = useEditor({
        immediatelyRender: false, // Fix SSR hydration mismatch
        editable: !readOnly,
        extensions: [
            StarterKit.configure({
                heading: {
                    levels: [1, 2, 3],
                },
                link: false,
            }),
            Link.configure({
                openOnClick: false,
                HTMLAttributes: {
                    class: 'text-primary underline cursor-pointer',
                },
            }),
            Placeholder.configure({
                placeholder,
            }),
            CommentMark,
        ],
        ...(content ? { content } : {}),
        editorProps: {
            attributes: {
                class: cn(
                    'prose prose-sm max-w-none focus:outline-none px-4 py-3',
                    'prose-headings:font-semibold prose-headings:text-foreground',
                    'prose-h1:text-xl prose-h1:mb-3 prose-h1:mt-4',
                    'prose-h2:text-lg prose-h2:mb-2 prose-h2:mt-3',
                    'prose-h3:text-base prose-h3:mb-2 prose-h3:mt-2',
                    'prose-p:my-2 prose-p:leading-relaxed',
                    'prose-ul:my-2 prose-ol:my-2',
                    'prose-li:my-0.5',
                ),
                style: `min-height: ${minHeight}`,
            },
            handleClick: (view, pos, event) => {
                // Handle comment clicks
                if (onCommentClick && event.target instanceof HTMLElement) {
                    const commentSpan = event.target.closest('[data-comment-id]')
                    if (commentSpan) {
                        const commentId = commentSpan.getAttribute('data-comment-id')
                        if (commentId) {
                            onCommentClick(commentId)
                            return true
                        }
                    }
                }
                return false
            },
        },
        onUpdate: ({ editor }) => {
            if (onChange) {
                const json = editor.getJSON()
                if (isTipTapDoc(json)) {
                    onChange(json)
                }
            }
        },
    })

    useSyncTipTapJsonContent(editor, content)

    const toolbarState = useEditorState({
        editor,
        selector: ({ editor: currentEditor }) => ({
            isHeading1: currentEditor?.isActive('heading', { level: 1 }) ?? false,
            isHeading2: currentEditor?.isActive('heading', { level: 2 }) ?? false,
            isHeading3: currentEditor?.isActive('heading', { level: 3 }) ?? false,
            isBold: currentEditor?.isActive('bold') ?? false,
            isItalic: currentEditor?.isActive('italic') ?? false,
            isUnderline: currentEditor?.isActive('underline') ?? false,
            isBulletList: currentEditor?.isActive('bulletList') ?? false,
            isOrderedList: currentEditor?.isActive('orderedList') ?? false,
            isLink: currentEditor?.isActive('link') ?? false,
            canUndo: currentEditor?.can().undo() ?? false,
            canRedo: currentEditor?.can().redo() ?? false,
            hasSelection: currentEditor ? !currentEditor.state.selection.empty : false,
        }),
    })

    const addLink = () => {
        if (!editor) return
        const previousUrl = editor.getAttributes('link').href || ''
        const url = window.prompt('Enter URL:', previousUrl)

        if (url === null) return
        if (url === '') {
            editor.chain().focus().extendMarkRange('link').unsetLink().run()
            return
        }

        editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
    }

    const addComment = () => {
        if (!editor || !onAddComment) return

        const { from, to } = editor.state.selection
        if (from === to) {
            // No selection
            return
        }

        const selectedText = editor.state.doc.textBetween(from, to, ' ')
        if (!selectedText.trim()) return

        // Generate a unique comment ID
        const commentId = crypto.randomUUID()

        // Add comment mark to the selected text
        editor.chain().focus().setMark('comment', { commentId }).run()

        // Notify parent component (which can then create the note)
        onAddComment(selectedText, commentId)
    }

    if (!editor || !toolbarState) return null

    if (readOnly) {
        return (
            <div className={cn('overflow-y-auto', className)} style={{ maxHeight }}>
                <EditorContent editor={editor} />
            </div>
        )
    }

    return (
        <div className={cn('border rounded-lg bg-background', className)}>
            {/* Toolbar */}
            <div className="flex flex-wrap items-center gap-1 border-b px-2 py-1.5 bg-muted/30 rounded-t-lg">
                {/* Headings */}
                <Toggle
                    size="sm"
                    pressed={toolbarState.isHeading1}
                    onPressedChange={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                    aria-label="Heading 1"
                    title="Heading 1"
                >
                    <Heading1Icon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={toolbarState.isHeading2}
                    onPressedChange={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                    aria-label="Heading 2"
                    title="Heading 2"
                >
                    <Heading2Icon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={toolbarState.isHeading3}
                    onPressedChange={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
                    aria-label="Heading 3"
                    title="Heading 3"
                >
                    <Heading3Icon className="size-4" />
                </Toggle>

                <div className="w-px h-4 bg-border mx-1" />

                {/* Text formatting */}
                <Toggle
                    size="sm"
                    pressed={toolbarState.isBold}
                    onPressedChange={() => editor.chain().focus().toggleBold().run()}
                    aria-label="Bold"
                    title="Bold (Ctrl+B)"
                >
                    <BoldIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={toolbarState.isItalic}
                    onPressedChange={() => editor.chain().focus().toggleItalic().run()}
                    aria-label="Italic"
                    title="Italic (Ctrl+I)"
                >
                    <ItalicIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={toolbarState.isUnderline}
                    onPressedChange={() => editor.chain().focus().toggleUnderline().run()}
                    aria-label="Underline"
                    title="Underline (Ctrl+U)"
                >
                    <UnderlineIcon className="size-4" />
                </Toggle>

                <div className="w-px h-4 bg-border mx-1" />

                {/* Lists */}
                <Toggle
                    size="sm"
                    pressed={toolbarState.isBulletList}
                    onPressedChange={() => editor.chain().focus().toggleBulletList().run()}
                    aria-label="Bullet List"
                    title="Bullet List"
                >
                    <ListIcon className="size-4" />
                </Toggle>
                <Toggle
                    size="sm"
                    pressed={toolbarState.isOrderedList}
                    onPressedChange={() => editor.chain().focus().toggleOrderedList().run()}
                    aria-label="Ordered List"
                    title="Numbered List"
                >
                    <ListOrderedIcon className="size-4" />
                </Toggle>

                <div className="w-px h-4 bg-border mx-1" />

                {/* Link */}
                <Toggle
                    size="sm"
                    pressed={toolbarState.isLink}
                    onPressedChange={addLink}
                    aria-label="Add Link"
                    title="Add Link"
                >
                    <LinkIcon className="size-4" />
                </Toggle>

                <div className="w-px h-4 bg-border mx-1" />

                {/* Undo/Redo */}
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => editor.chain().focus().undo().run()}
                    disabled={!toolbarState.canUndo}
                    className="size-8 p-0"
                    aria-label="Undo"
                    title="Undo (Ctrl+Z)"
                >
                    <Undo2Icon className="size-4" />
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => editor.chain().focus().redo().run()}
                    disabled={!toolbarState.canRedo}
                    className="size-8 p-0"
                    aria-label="Redo"
                    title="Redo (Ctrl+Shift+Z)"
                >
                    <Redo2Icon className="size-4" />
                </Button>

                {/* Add Comment (when enabled and text is selected) */}
                {showComments && onAddComment && (
                    <>
                        <div className="w-px h-4 bg-border mx-1" />
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={addComment}
                            disabled={!toolbarState.hasSelection}
                            className="size-8 p-0"
                            aria-label="Add Comment"
                            title="Add Comment (select text first)"
                        >
                            <MessageSquareIcon className="size-4" />
                        </Button>
                    </>
                )}
            </div>

            {/* Editor Content - with scroll support */}
            <div className="overflow-y-auto rounded-b-lg" style={{ maxHeight }}>
                <EditorContent editor={editor} />
            </div>
        </div>
    )
}
