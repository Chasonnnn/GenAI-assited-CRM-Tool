import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    createEmailTemplateDraft,
    createEmailTemplateDraftFromTemplate,
    discardEmailTemplateDraft,
    getEmailTemplateDraft,
    listEmailTemplateDrafts,
    publishEmailTemplateDraft,
    restoreEmailTemplateDraftVersion,
    sendTestEmailTemplateDraft,
    updateEmailTemplateDraft,
    type EmailTemplateDraft,
} from "@/lib/api/email-template-drafts"
import {
    emailTemplateDraftKeys,
    useCreateEmailTemplateDraft,
    useCreateEmailTemplateDraftFromTemplate,
    useDiscardEmailTemplateDraft,
    useEmailTemplateDraft,
    useEmailTemplateDrafts,
    usePublishEmailTemplateDraft,
    useRestoreEmailTemplateDraftVersion,
    useSendTestEmailTemplateDraft,
    useUpdateEmailTemplateDraft,
} from "@/lib/hooks/use-email-template-drafts"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/email-template-drafts", async (importOriginal) => {
    const actual =
        await importOriginal<typeof import("@/lib/api/email-template-drafts")>()
    return {
        ...actual,
        createEmailTemplateDraft: vi.fn(),
        createEmailTemplateDraftFromTemplate: vi.fn(),
        discardEmailTemplateDraft: vi.fn(),
        getEmailTemplateDraft: vi.fn(),
        listEmailTemplateDrafts: vi.fn(),
        publishEmailTemplateDraft: vi.fn(),
        restoreEmailTemplateDraftVersion: vi.fn(),
        sendTestEmailTemplateDraft: vi.fn(),
        updateEmailTemplateDraft: vi.fn(),
    }
})

function createQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    })
}

function wrapperFor(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
    }
}

const draft = {
    id: "draft-1",
    template_id: "template-1",
    revision: 3,
    published_version: 7,
} as EmailTemplateDraft

describe("email template draft hooks", () => {
    beforeEach(() => {
        vi.mocked(createEmailTemplateDraft).mockReset()
        vi.mocked(createEmailTemplateDraft).mockResolvedValue(draft)
        vi.mocked(createEmailTemplateDraftFromTemplate).mockReset()
        vi.mocked(createEmailTemplateDraftFromTemplate).mockResolvedValue(draft)
        vi.mocked(discardEmailTemplateDraft).mockReset()
        vi.mocked(discardEmailTemplateDraft).mockResolvedValue(undefined)
        vi.mocked(getEmailTemplateDraft).mockReset()
        vi.mocked(getEmailTemplateDraft).mockResolvedValue(draft)
        vi.mocked(listEmailTemplateDrafts).mockReset()
        vi.mocked(listEmailTemplateDrafts).mockResolvedValue([draft])
        vi.mocked(publishEmailTemplateDraft).mockReset()
        vi.mocked(publishEmailTemplateDraft).mockResolvedValue({
            id: "template-1",
        } as never)
        vi.mocked(restoreEmailTemplateDraftVersion).mockReset()
        vi.mocked(restoreEmailTemplateDraftVersion).mockResolvedValue(draft)
        vi.mocked(sendTestEmailTemplateDraft).mockReset()
        vi.mocked(sendTestEmailTemplateDraft).mockResolvedValue({
            success: true,
            queued: true,
            tested_revision: 3,
        })
        vi.mocked(updateEmailTemplateDraft).mockReset()
        vi.mocked(updateEmailTemplateDraft).mockResolvedValue(draft)
    })

    it("fetches the requested draft list and disables an empty detail query", async () => {
        const queryClient = createQueryClient()
        const wrapper = wrapperFor(queryClient)

        renderHook(
            () =>
                useEmailTemplateDrafts({
                    scope: "personal",
                    showAllPersonal: true,
                }),
            { wrapper },
        )
        renderHook(() => useEmailTemplateDraft(null), { wrapper })

        await waitFor(() => {
            expect(listEmailTemplateDrafts).toHaveBeenCalledWith({
                scope: "personal",
                showAllPersonal: true,
            })
        })
        expect(getEmailTemplateDraft).not.toHaveBeenCalled()
    })

    it("creates drafts through both entry points and refreshes draft lists", async () => {
        const createData = {
            name: "Journey update",
            subject: "Hello",
            body: "<p>Hello</p>",
            scope: "org" as const,
        }
        const queryClient = createQueryClient()
        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [])
        const wrapper = wrapperFor(queryClient)
        const create = renderHook(() => useCreateEmailTemplateDraft(), { wrapper })
        const fromTemplate = renderHook(
            () => useCreateEmailTemplateDraftFromTemplate(),
            { wrapper },
        )

        await act(async () => {
            await create.result.current.mutateAsync(createData)
        })
        expect(createEmailTemplateDraft).toHaveBeenCalledWith(createData)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))?.isInvalidated,
        ).toBe(true)

        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [])
        await act(async () => {
            await fromTemplate.result.current.mutateAsync({
                templateId: "template-1",
            })
        })
        expect(createEmailTemplateDraftFromTemplate).toHaveBeenCalledWith(
            "template-1",
        )
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))?.isInvalidated,
        ).toBe(true)
    })

    it("updates with expected_revision and refreshes both list and detail", async () => {
        const queryClient = createQueryClient()
        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [draft])
        queryClient.setQueryData(emailTemplateDraftKeys.detail(draft.id), draft)
        const view = renderHook(() => useUpdateEmailTemplateDraft(), {
            wrapper: wrapperFor(queryClient),
        })
        const data = {
            subject: "Revised",
            expected_revision: 3,
        }

        await act(async () => {
            await view.result.current.mutateAsync({ id: draft.id, data })
        })

        expect(updateEmailTemplateDraft).toHaveBeenCalledWith(draft.id, data)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.detail(draft.id))
                ?.isInvalidated,
        ).toBe(true)
    })

    it("discards the draft, refreshes lists, and removes its detail cache", async () => {
        const queryClient = createQueryClient()
        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [draft])
        queryClient.setQueryData(emailTemplateDraftKeys.detail(draft.id), draft)
        const view = renderHook(() => useDiscardEmailTemplateDraft(), {
            wrapper: wrapperFor(queryClient),
        })

        await act(async () => {
            await view.result.current.mutateAsync({
                id: draft.id,
                expectedRevision: draft.revision,
            })
        })

        expect(discardEmailTemplateDraft).toHaveBeenCalledWith(
            draft.id,
            draft.revision,
        )
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.detail(draft.id)),
        ).toBeUndefined()
    })

    it("publishes with both version fences and refreshes draft and published-template caches", async () => {
        const queryClient = createQueryClient()
        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [draft])
        queryClient.setQueryData(emailTemplateDraftKeys.detail(draft.id), draft)
        queryClient.setQueryData(["email-templates", "list"], [])
        const view = renderHook(() => usePublishEmailTemplateDraft(), {
            wrapper: wrapperFor(queryClient),
        })
        const data = {
            expected_revision: 3,
            expected_published_version: 7,
        }

        await act(async () => {
            await view.result.current.mutateAsync({ id: draft.id, data })
        })

        expect(publishEmailTemplateDraft).toHaveBeenCalledWith(draft.id, data)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.detail(draft.id)),
        ).toBeUndefined()
        expect(
            queryClient.getQueryState(["email-templates", "list"])?.isInvalidated,
        ).toBe(true)
    })

    it("restores history into the draft and refreshes draft caches", async () => {
        const queryClient = createQueryClient()
        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [draft])
        queryClient.setQueryData(emailTemplateDraftKeys.detail(draft.id), draft)
        const view = renderHook(() => useRestoreEmailTemplateDraftVersion(), {
            wrapper: wrapperFor(queryClient),
        })
        const data = {
            target_version: 2,
            expected_revision: draft.revision,
        }

        await act(async () => {
            await view.result.current.mutateAsync({ id: draft.id, data })
        })

        expect(restoreEmailTemplateDraftVersion).toHaveBeenCalledWith(
            draft.id,
            data,
        )
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))
                ?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.detail(draft.id))
                ?.isInvalidated,
        ).toBe(true)
    })

    it("test-sends the draft and refreshes its tested-revision metadata", async () => {
        const queryClient = createQueryClient()
        queryClient.setQueryData(emailTemplateDraftKeys.list({}), [draft])
        queryClient.setQueryData(emailTemplateDraftKeys.detail(draft.id), draft)
        const view = renderHook(() => useSendTestEmailTemplateDraft(), {
            wrapper: wrapperFor(queryClient),
        })
        const payload = {
            to_email: "reviewer@example.com",
            idempotency_key: "template-draft-test/123",
            expected_revision: 3,
        }

        await act(async () => {
            await view.result.current.mutateAsync({ id: draft.id, payload })
        })

        expect(sendTestEmailTemplateDraft).toHaveBeenCalledWith(draft.id, payload)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.list({}))?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailTemplateDraftKeys.detail(draft.id))
                ?.isInvalidated,
        ).toBe(true)
    })
})
