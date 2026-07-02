/**
 * Utility functions for working with TipTap transcript documents.
 * These are separated from TranscriptEditor to avoid bundling TipTap
 * when only the utility functions are needed.
 */

import type { TipTapDoc } from "@/lib/api/interviews"

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
