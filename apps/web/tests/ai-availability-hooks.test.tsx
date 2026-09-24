import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import * as aiApi from "@/lib/api/ai"
import { useAIAvailability, useUpdateAISettings } from "@/lib/hooks/use-ai"

vi.unmock("@tanstack/react-query")
vi.mock("@/lib/api/ai", () => ({
    getAIAvailability: vi.fn(),
    getAISettings: vi.fn(),
    updateAISettings: vi.fn(),
}))

describe("AI availability", () => {
    it("uses the staff endpoint and refreshes availability after an organization setting change", async () => {
        const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
        const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        vi.mocked(aiApi.getAIAvailability).mockResolvedValue({ is_enabled: true, provider: "gemini", model: "test-model" })
        const view = renderHook(() => ({ availability: useAIAvailability(), update: useUpdateAISettings() }), { wrapper })
        await waitFor(() => expect(view.result.current.availability.data?.is_enabled).toBe(true))
        expect(aiApi.getAISettings).not.toHaveBeenCalled()
        vi.mocked(aiApi.getAIAvailability).mockResolvedValue({ is_enabled: false, provider: "gemini", model: "test-model" })
        vi.mocked(aiApi.updateAISettings).mockResolvedValue({ is_enabled: false } as aiApi.AISettings)
        await act(async () => { await view.result.current.update.mutateAsync({ is_enabled: false }) })
        await waitFor(() => expect(view.result.current.availability.data?.is_enabled).toBe(false))
        queryClient.clear()
    })
})
