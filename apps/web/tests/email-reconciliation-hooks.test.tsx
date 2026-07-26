import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    confirmEmailReconciliationNotSent,
    confirmEmailReconciliationSent,
    dismissEmailReconciliationCase,
    getEmailReconciliationCases,
    linkEmailReconciliationEvent,
    retryEmailReconciliationCorrelation,
} from "@/lib/api/email-operations"
import {
    emailOperationsKeys,
    useConfirmEmailReconciliationNotSent,
    useConfirmEmailReconciliationSent,
    useDismissEmailReconciliationCase,
    useEmailReconciliationCases,
    useLinkEmailReconciliationEvent,
    useRetryEmailReconciliationCorrelation,
} from "@/lib/hooks/use-email-operations"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/email-operations", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api/email-operations")>()
    return {
        ...actual,
        confirmEmailReconciliationNotSent: vi.fn(),
        confirmEmailReconciliationSent: vi.fn(),
        getEmailReconciliationCases: vi.fn(),
        dismissEmailReconciliationCase: vi.fn(),
        retryEmailReconciliationCorrelation: vi.fn(),
        linkEmailReconciliationEvent: vi.fn(),
    }
})

function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
        },
    })

    return function Wrapper({ children }: { children: ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
    }
}

describe("email reconciliation hooks", () => {
    beforeEach(() => {
        vi.mocked(getEmailReconciliationCases).mockReset()
        vi.mocked(getEmailReconciliationCases).mockResolvedValue({
            items: [],
            next_cursor: null,
            counts: {
                monitoring: 0,
                action_required: 0,
                resolved: 0,
            },
        })
        vi.mocked(retryEmailReconciliationCorrelation).mockReset()
        vi.mocked(retryEmailReconciliationCorrelation).mockResolvedValue({} as never)
        vi.mocked(dismissEmailReconciliationCase).mockReset()
        vi.mocked(dismissEmailReconciliationCase).mockResolvedValue({} as never)
        vi.mocked(linkEmailReconciliationEvent).mockReset()
        vi.mocked(linkEmailReconciliationEvent).mockResolvedValue({} as never)
        vi.mocked(confirmEmailReconciliationSent).mockReset()
        vi.mocked(confirmEmailReconciliationSent).mockResolvedValue({} as never)
        vi.mocked(confirmEmailReconciliationNotSent).mockReset()
        vi.mocked(confirmEmailReconciliationNotSent).mockResolvedValue({} as never)
    })

    it("does not fetch the operator queue until permission enables it", async () => {
        const view = renderHook(
            ({ enabled }) =>
                useEmailReconciliationCases({
                    enabled,
                    status: "action_required",
                }),
            {
                initialProps: { enabled: false },
                wrapper: createWrapper(),
            },
        )

        await Promise.resolve()
        expect(getEmailReconciliationCases).not.toHaveBeenCalled()

        view.rerender({ enabled: true })

        await waitFor(() => {
            expect(getEmailReconciliationCases).toHaveBeenCalledWith({
                status: "action_required",
                limit: 25,
            })
        })
    })

    it("refreshes reconciliation, readiness, and messages after a retry", async () => {
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        queryClient.setQueryData(
            emailOperationsKeys.reconciliationCases("action_required"),
            { items: [] },
        )
        queryClient.setQueryData(emailOperationsKeys.readiness(), { overall: "ready" })
        queryClient.setQueryData(emailOperationsKeys.messages(), { pages: [] })

        const wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
        const view = renderHook(() => useRetryEmailReconciliationCorrelation(), { wrapper })

        await act(async () => {
            await view.result.current.mutateAsync({
                caseId: "case-1",
                expectedVersion: 4,
            })
        })

        expect(vi.mocked(retryEmailReconciliationCorrelation).mock.calls[0]?.[0]).toEqual({
            caseId: "case-1",
            expectedVersion: 4,
        })
        expect(
            queryClient.getQueryState(
                emailOperationsKeys.reconciliationCases("action_required"),
            )?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.readiness())?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.messages())?.isInvalidated,
        ).toBe(true)
    })

    it("refreshes the reconciliation queue after a controlled dismissal", async () => {
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        const actionRequiredKey =
            emailOperationsKeys.reconciliationCases("action_required")
        queryClient.setQueryData(actionRequiredKey, { items: [] })

        const wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
        const view = renderHook(() => useDismissEmailReconciliationCase(), { wrapper })

        await act(async () => {
            await view.result.current.mutateAsync({
                caseId: "case-2",
                expectedVersion: 5,
                resolutionCode: "test_event",
            })
        })

        expect(vi.mocked(dismissEmailReconciliationCase).mock.calls[0]?.[0]).toEqual({
            caseId: "case-2",
            expectedVersion: 5,
            resolutionCode: "test_event",
        })
        expect(queryClient.getQueryState(actionRequiredKey)?.isInvalidated).toBe(true)
    })

    it("refreshes reconciliation and delivery evidence after linking an event", async () => {
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        const actionRequiredKey =
            emailOperationsKeys.reconciliationCases("action_required")
        queryClient.setQueryData(actionRequiredKey, { items: [] })
        queryClient.setQueryData(emailOperationsKeys.readiness(), { overall: "ready" })
        queryClient.setQueryData(emailOperationsKeys.messages(), { pages: [] })

        const wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
        const view = renderHook(() => useLinkEmailReconciliationEvent(), { wrapper })

        await act(async () => {
            await view.result.current.mutateAsync({
                caseId: "case-3",
                expectedVersion: 6,
                emailLogId: "message-3",
            })
        })

        expect(vi.mocked(linkEmailReconciliationEvent).mock.calls[0]?.[0]).toEqual({
            caseId: "case-3",
            expectedVersion: 6,
            emailLogId: "message-3",
        })
        expect(queryClient.getQueryState(actionRequiredKey)?.isInvalidated).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.readiness())?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.messages())?.isInvalidated,
        ).toBe(true)
    })

    it("refreshes reconciliation and delivery evidence after confirming sent", async () => {
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        const actionRequiredKey =
            emailOperationsKeys.reconciliationCases("action_required")
        queryClient.setQueryData(actionRequiredKey, { items: [] })
        queryClient.setQueryData(emailOperationsKeys.readiness(), { overall: "ready" })
        queryClient.setQueryData(emailOperationsKeys.messages(), { pages: [] })

        const wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
        const view = renderHook(() => useConfirmEmailReconciliationSent(), { wrapper })

        await act(async () => {
            await view.result.current.mutateAsync({
                caseId: "case-4",
                expectedVersion: 7,
                providerMessageId: "provider-message-4",
            })
        })

        expect(vi.mocked(confirmEmailReconciliationSent).mock.calls[0]?.[0]).toEqual({
            caseId: "case-4",
            expectedVersion: 7,
            providerMessageId: "provider-message-4",
        })
        expect(queryClient.getQueryState(actionRequiredKey)?.isInvalidated).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.readiness())?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.messages())?.isInvalidated,
        ).toBe(true)
    })

    it("refreshes reconciliation and delivery evidence after confirming not sent", async () => {
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        const actionRequiredKey =
            emailOperationsKeys.reconciliationCases("action_required")
        queryClient.setQueryData(actionRequiredKey, { items: [] })
        queryClient.setQueryData(emailOperationsKeys.readiness(), { overall: "ready" })
        queryClient.setQueryData(emailOperationsKeys.messages(), { pages: [] })

        const wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
        const view = renderHook(() => useConfirmEmailReconciliationNotSent(), {
            wrapper,
        })

        await act(async () => {
            await view.result.current.mutateAsync({
                caseId: "case-5",
                expectedVersion: 8,
            })
        })

        expect(vi.mocked(confirmEmailReconciliationNotSent).mock.calls[0]?.[0]).toEqual({
            caseId: "case-5",
            expectedVersion: 8,
        })
        expect(queryClient.getQueryState(actionRequiredKey)?.isInvalidated).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.readiness())?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.messages())?.isInvalidated,
        ).toBe(true)
    })
})
