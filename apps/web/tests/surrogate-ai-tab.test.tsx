import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import type { ComponentProps } from "react"
import { SurrogateAiTab } from "@/components/surrogates/detail/SurrogateAiTab"

describe("SurrogateAiTab", () => {
    function renderEnabledTab(
        overrides: Partial<ComponentProps<typeof SurrogateAiTab>> = {}
    ) {
        return render(
            <SurrogateAiTab
                aiSettings={{ is_enabled: true }}
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

    it("renders disabled state when AI is not enabled", () => {
        render(
            <SurrogateAiTab
                aiSettings={{ is_enabled: false }}
                aiSummary={null}
                aiDraftEmail={null}
                selectedEmailType={null}
                onSelectEmailType={() => {}}
                onGenerateSummary={() => {}}
                onDraftEmail={() => {}}
                summaryStatus="idle"
                draftEmailStatus="idle"
            />
        )

        expect(screen.getByText("AI Assistant Not Enabled")).toBeInTheDocument()
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
