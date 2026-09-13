import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import SurrogateAiPage from "@/app/(app)/surrogates/[id]/ai/page"

const availability = vi.fn()
const summarize = vi.fn()
const draft = vi.fn()

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }) }))
vi.mock("@/components/ui/tabs", () => ({ TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div> }))
vi.mock("@/lib/hooks/use-ai", () => ({
    useAIAvailability: () => availability(),
    useSummarizeSurrogate: () => ({ mutateAsync: summarize, isPending: false }),
    useDraftEmail: () => ({ mutateAsync: draft, isPending: false }),
}))

describe("Surrogate AI availability", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        availability.mockReturnValue({ data: { is_enabled: true }, isPending: false, isError: false })
    })

    it("waits for staff availability before showing generation controls", () => {
        availability.mockReturnValue({ data: undefined, isPending: true })
        render(<SurrogateAiPage />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading AI Assistant")
        expect(screen.queryByRole("button", { name: /Generate Summary/i })).not.toBeInTheDocument()
    })

    it("supports retry when availability fails", () => {
        const refetch = vi.fn()
        availability.mockReturnValue({ data: undefined, isError: true, refetch })
        render(<SurrogateAiPage />)
        expect(screen.getByRole("alert")).toHaveTextContent("AI Assistant unavailable")
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(refetch).toHaveBeenCalled()
    })

    it("removes generation controls when organization AI is switched off", () => {
        const view = render(<SurrogateAiPage />)
        expect(screen.getByRole("button", { name: /Generate Summary/i })).toBeEnabled()
        availability.mockReturnValue({ data: { is_enabled: false } })
        view.rerender(<SurrogateAiPage />)
        expect(screen.getByText("AI Assistant Not Enabled")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Generate Summary/i })).not.toBeInTheDocument()
        expect(summarize).not.toHaveBeenCalled()
        expect(draft).not.toHaveBeenCalled()
    })
})
