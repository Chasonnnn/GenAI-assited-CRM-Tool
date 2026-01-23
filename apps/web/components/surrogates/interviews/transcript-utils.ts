/**
 * Utility functions for working with TipTap transcript documents.
 * These are separated from TranscriptEditor to avoid bundling TipTap
 * when only the utility functions are needed.
 */

import type { TipTapDoc, TipTapNode, TipTapMark } from "@/lib/api/interviews"

/**
 * Helper to check if a TipTap document is empty.
 */
export function isTranscriptEmpty(doc: TipTapDoc | null | undefined): boolean {
    if (!doc || !doc.content || doc.content.length === 0) return true

    // Check if all content is empty paragraphs
    return doc.content.every((node) => {
        if (node.type === "paragraph") {
            if (!node.content || node.content.length === 0) return true
            return node.content.every((child) => {
                if (child.type === "text") {
                    return !child.text || child.text.trim() === ""
                }
                return false
            })
        }
        return false
    })
}

/**
 * Extract all comment IDs from a TipTap document.
 * Returns a Set of comment IDs found in comment marks.
 */
export function extractCommentIds(doc: TipTapDoc | null | undefined): Set<string> {
    const commentIds = new Set<string>()
    if (!doc || !doc.content) return commentIds

    function extractFromNode(node: TipTapNode): void {
        // Check for comment marks on text nodes
        if (node.type === "text" && node.marks) {
            for (const mark of node.marks) {
                const commentId =
                    mark.type === "comment" && typeof mark.attrs?.commentId === "string"
                        ? mark.attrs.commentId
                        : null
                if (commentId) {
                    commentIds.add(commentId)
                }
            }
        }

        // Recurse into content
        if (node.content) {
            for (const child of node.content) {
                extractFromNode(child)
            }
        }
    }

    for (const node of doc.content) {
        extractFromNode(node)
    }

    return commentIds
}

/**
 * Remove a comment mark from a TipTap document by commentId.
 * Returns a new document with the comment mark removed.
 */
export function removeCommentFromDoc(doc: TipTapDoc, commentId: string): TipTapDoc {
    function processNode(node: TipTapNode): TipTapNode {
        const newNode: TipTapNode = { ...node }

        // Remove comment mark if it matches
        if (newNode.marks) {
            newNode.marks = newNode.marks.filter(
                (mark: TipTapMark) => !(mark.type === "comment" && mark.attrs?.commentId === commentId)
            )
            if (newNode.marks.length === 0) {
                delete newNode.marks
            }
        }

        // Process child content
        if (newNode.content) {
            newNode.content = newNode.content.map(processNode)
        }

        return newNode
    }

    return {
        ...doc,
        content: doc.content?.map(processNode) || [],
    }
}
