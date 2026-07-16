import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useEmailAttachmentSelectionNotification } from "@/lib/hooks/use-email-attachment-selection-notification"

describe("useEmailAttachmentSelectionNotification", () => {
    it("notifies the parent whenever derived attachment safety changes", () => {
        const onSelectionChange = vi.fn()
        const { rerender } = renderHook(
            ({ hasBlockingAttachments }) =>
                useEmailAttachmentSelectionNotification({
                    selectedAttachmentIds: ["att-1"],
                    hasBlockingAttachments,
                    totalBytes: 1024,
                    errorMessage: hasBlockingAttachments
                        ? "All selected attachments must be clean before sending."
                        : null,
                    onSelectionChange,
                }),
            {
                initialProps: { hasBlockingAttachments: false },
            },
        )

        expect(onSelectionChange).toHaveBeenLastCalledWith({
            selectedAttachmentIds: ["att-1"],
            hasBlockingAttachments: false,
            totalBytes: 1024,
            errorMessage: null,
        })

        rerender({ hasBlockingAttachments: true })

        expect(onSelectionChange).toHaveBeenLastCalledWith({
            selectedAttachmentIds: ["att-1"],
            hasBlockingAttachments: true,
            totalBytes: 1024,
            errorMessage: "All selected attachments must be clean before sending.",
        })
    })
})
