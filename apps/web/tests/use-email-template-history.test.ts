import { beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
    useEmailTemplateVersions,
    useRollbackEmailTemplate,
    useUpdateEmailTemplate,
} from "@/lib/hooks/use-email-templates"

type MutationOptions = {
    onSuccess?: (
        data: unknown,
        variables: { id: string; version?: number; data?: unknown },
    ) => void
}

describe("email template history hooks", () => {
    const invalidateQueries = vi.fn()
    let capturedMutation: MutationOptions | null = null

    beforeEach(() => {
        invalidateQueries.mockReset()
        capturedMutation = null

        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
        } as unknown as ReturnType<typeof useQueryClient>)
        vi.mocked(useQuery).mockImplementation((options: unknown) => (
            options as ReturnType<typeof useQuery>
        ))
        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedMutation = options as MutationOptions
            return {
                mutateAsync: vi.fn(),
                isPending: false,
            } as unknown as ReturnType<typeof useMutation>
        })
    })

    it("does not fetch history until an existing editor opens it", () => {
        const query = useEmailTemplateVersions("template-1", false) as unknown as {
            queryKey: readonly unknown[]
            enabled: boolean
        }

        expect(query.queryKey).toEqual([
            "email-templates",
            "versions",
            "template-1",
        ])
        expect(query.enabled).toBe(false)
    })

    it("invalidates the list, detail, and history after a restore", () => {
        useRollbackEmailTemplate()

        capturedMutation?.onSuccess?.(
            {},
            { id: "template-1", version: 2 },
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ["email-templates", "list"],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ["email-templates", "detail", "template-1"],
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ["email-templates", "versions", "template-1"],
        })
    })

    it("invalidates history after saving another edit", () => {
        useUpdateEmailTemplate()

        capturedMutation?.onSuccess?.(
            {},
            { id: "template-1", data: { subject: "Updated subject" } },
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ["email-templates", "versions", "template-1"],
        })
    })
})
