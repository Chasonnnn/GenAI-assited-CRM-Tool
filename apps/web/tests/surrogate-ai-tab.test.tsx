import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { SurrogateAiTab } from "@/components/surrogates/detail/SurrogateAiTab"

describe("SurrogateAiTab", () => {
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
                isGeneratingSummary={false}
                isDraftingEmail={false}
            />
        )

        expect(screen.getByText("AI Assistant Not Enabled")).toBeInTheDocument()
    })

    it("triggers summary generation when enabled", () => {
        const onGenerateSummary = vi.fn()

        render(
            <SurrogateAiTab
                aiSettings={{ is_enabled: true }}
                aiSummary={null}
                aiDraftEmail={null}
                selectedEmailType={null}
                onSelectEmailType={() => {}}
                onGenerateSummary={onGenerateSummary}
                onDraftEmail={() => {}}
                isGeneratingSummary={false}
                isDraftingEmail={false}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /Generate Summary/i }))
        expect(onGenerateSummary).toHaveBeenCalled()
    })
})
