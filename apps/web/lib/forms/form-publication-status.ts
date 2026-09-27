import { hashKey } from "@tanstack/react-query"

export type FormPublicationStatus = "draft" | "published" | "unpublished_changes"

export const FORM_PUBLICATION_STATUS_LABELS: Record<FormPublicationStatus, string> = {
    draft: "Draft",
    published: "Published",
    unpublished_changes: "Unpublished changes",
}

// hashKey is TanStack Query's stable JSON serializer: it sorts plain-object keys, so
// payloads with the same content in a different key order compare equal.
export function hasSameContent(left: unknown, right: unknown): boolean {
    return hashKey([left]) === hashKey([right])
}

export function getFormPublicationStatus(
    isPublished: boolean,
    hasUnpublishedChanges: boolean,
): FormPublicationStatus {
    if (!isPublished) return "draft"
    return hasUnpublishedChanges ? "unpublished_changes" : "published"
}
