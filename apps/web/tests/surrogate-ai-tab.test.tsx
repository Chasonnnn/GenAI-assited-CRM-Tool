import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { ComponentProps } from "react"
import { SurrogateAiTab } from "@/components/surrogates/detail/SurrogateAiTab"

vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

describe("SurrogateAiTab", () => {
    function renderEnabledTab(
        overrides: Partial<ComponentProps<typeof SurrogateAiTab>> = {}
    ) {
        return render(
            <SurrogateAiTab
                aiEnabled
                canManageAI={false}
                aiSummary={null}
                aiDraftEmail={null}
                selectedEmailType={null}
                onSelectEmailType={() => {}}
                onGenerateSummary={() => {}}
                onDraftEmail={() => {}}
                summaryStatus="idle"
                draftEmailStatus="idle"
                {...overrides}
            />
        )
    }

    it("sends admins to the AI settings when AI is off", () => {
        renderEnabledTab({ aiEnabled: false, canManageAI: true })

        expect(screen.getByRole("heading", { name: "AI is off" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Open AI settings" })).toHaveAttribute(
            "href",
            "/settings/integrations",
        )
        expect(screen.queryByText(/contact your admin/i)).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /generate summary/i })).not.toBeInTheDocument()
    })

    it("tells other roles AI is off for the organization without a settings link", () => {
        renderEnabledTab({ aiEnabled: false, canManageAI: false })

        expect(screen.getByRole("heading", { name: "AI is off for this organization" })).toBeInTheDocument()
        expect(screen.queryByRole("link", { name: "Open AI settings" })).not.toBeInTheDocument()
    })

    it("triggers summary generation when enabled", () => {
        const onGenerateSummary = vi.fn()

        renderEnabledTab({ onGenerateSummary })

        fireEvent.click(screen.getByRole("button", { name: /Generate Summary/i }))
        expect(onGenerateSummary).toHaveBeenCalled()
    })

    it("shows the generating summary state", () => {
        renderEnabledTab({ summaryStatus: "generating" })

        const button = screen.getByRole("button", { name: /Generating/i })
        expect(button).toBeDisabled()
    })

    it("disables draft email until an email type is selected", () => {
        renderEnabledTab()

        expect(screen.getByRole("button", { name: /Draft Email/i })).toBeDisabled()
    })

    it("shows the drafting email state", () => {
        renderEnabledTab({
            selectedEmailType: "follow_up",
            draftEmailStatus: "drafting",
        })

        const button = screen.getByRole("button", { name: /Drafting/i })
        expect(button).toBeDisabled()
    })
})
