import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAuditExports } from "@/lib/hooks/use-audit"

const listAuditExportsMock = vi.hoisted(() => vi.fn())

vi.unmock("@tanstack/react-query")
vi.mock("@/lib/api/audit", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/audit")>("@/lib/api/audit")
    return {
        ...actual,
        listAuditExports: listAuditExportsMock,
    }
})

function AuditExportsHarness({ includeFull = false }: { includeFull?: boolean }) {
    useAuditExports({ includeFull })
    return null
}

describe("audit export polling", () => {
    beforeEach(() => {
        vi.useFakeTimers({ shouldAdvanceTime: true })
        listAuditExportsMock.mockReset()
        listAuditExportsMock.mockResolvedValue({
            items: [
                {
                    id: "export-1",
                    status: "processing",
                    redact_mode: "redacted",
                },
            ],
        })
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("refetches while a visible export job is processing", async () => {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })
        render(
            <QueryClientProvider client={queryClient}>
                <AuditExportsHarness />
            </QueryClientProvider>
        )

        await waitFor(() => expect(listAuditExportsMock).toHaveBeenCalledTimes(1))

        await vi.advanceTimersByTimeAsync(8000)

        await waitFor(() => expect(listAuditExportsMock).toHaveBeenCalledTimes(2))
    })

    it("does not poll a hidden full-data export for non-developers", async () => {
        listAuditExportsMock.mockResolvedValue({
            items: [
                {
                    id: "export-1",
                    status: "processing",
                    redact_mode: "full",
                },
            ],
        })
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })
        render(
            <QueryClientProvider client={queryClient}>
                <AuditExportsHarness />
            </QueryClientProvider>
        )

        await waitFor(() => expect(listAuditExportsMock).toHaveBeenCalledTimes(1))
        await vi.advanceTimersByTimeAsync(16000)

        expect(listAuditExportsMock).toHaveBeenCalledTimes(1)
    })
})
