import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import SurrogateAiPage from "@/app/(app)/surrogates/[id]/ai/page"

const availability = vi.fn()
const summarize = vi.fn()
const draft = vi.fn()
const permissions = vi.fn<() => string[]>()

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }) }))
vi.mock("@/components/ui/tabs", () => ({ TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div> }))
vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))
vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({ can: (key: string) => permissions().includes(key) }),
}))
vi.mock("@/lib/hooks/use-ai", () => ({
    useAIAvailability: () => availability(),
    useSummarizeSurrogate: () => ({ mutateAsync: summarize, isPending: false }),
    useDraftEmail: () => ({ mutateAsync: draft, isPending: false }),
}))

describe("Surrogate AI availability", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        availability.mockReturnValue({ data: { is_enabled: true }, isPending: false, isError: false })
        permissions.mockReturnValue([])
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
        expect(screen.getByRole("heading", { name: "AI is turned off for this organization." })).toBeInTheDocument()
        expect(screen.queryByRole("link", { name: "AI settings" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Generate Summary/i })).not.toBeInTheDocument()
        expect(summarize).not.toHaveBeenCalled()
        expect(draft).not.toHaveBeenCalled()
    })

    it("links to AI settings only when the viewer can manage integrations and AI settings", () => {
        availability.mockReturnValue({ data: { is_enabled: false }, isPending: false, isError: false })
        permissions.mockReturnValue(["manage_ai_settings"])
        const view = render(<SurrogateAiPage />)
        expect(screen.queryByRole("link", { name: "AI settings" })).not.toBeInTheDocument()

        permissions.mockReturnValue(["manage_integrations", "manage_ai_settings"])
        view.rerender(<SurrogateAiPage />)
        expect(screen.getByRole("link", { name: "AI settings" })).toHaveAttribute("href", "/settings/integrations")
    })
})
