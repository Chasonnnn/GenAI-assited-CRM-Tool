import type { ReactNode } from "react"
import { act, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"

import { useSessionExpirationDetection } from "@/lib/hooks/use-session-expiration-detection"

vi.unmock("@tanstack/react-query")

function createWrapper(queryClient: QueryClient) {
    return function QueryWrapper({ children }: { children: ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
    }
}

describe("useSessionExpirationDetection", () => {
    it("detects 401 errors from query and mutation caches", async () => {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
        const queryDetection = renderHook(
            () => useSessionExpirationDetection(),
            { wrapper: createWrapper(queryClient) }
        )

        expect(queryDetection.result.current).toBe(false)

        await act(async () => {
            await queryClient.fetchQuery({
                queryKey: ["expired-query"],
                queryFn: async () => {
                    throw { status: 401 }
                },
            }).catch(() => undefined)
        })

        expect(queryDetection.result.current).toBe(true)

        const mutationClient = new QueryClient({
            defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
        const mutationDetection = renderHook(
            () => useSessionExpirationDetection(),
            { wrapper: createWrapper(mutationClient) }
        )
        const mutation = mutationClient.getMutationCache().build(mutationClient, {
            mutationFn: async () => {
                throw { response: { status: 401 } }
            },
        })

        expect(mutationDetection.result.current).toBe(false)

        await act(async () => {
            await mutation.execute(undefined).catch(() => undefined)
        })

        expect(mutationDetection.result.current).toBe(true)
    })
})
