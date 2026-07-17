import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { IntelligentSuggestionsSection } from "../app/(app)/settings/intelligent-suggestions-section"

vi.unmock("@tanstack/react-query")

const getSettings = vi.fn()
const getTemplates = vi.fn()
const getRules = vi.fn()

vi.mock("@/lib/hooks/use-pipelines", () => ({
    usePipelines: () => ({
        data: [
            {
                stages: [
                    {
                        slug: "new_unread",
                        stage_key: "new_unread",
                        label: "New Unread",
                        is_active: true,
                    },
                ],
            },
        ],
    }),
}))

vi.mock("@/lib/api/settings", () => ({
    getIntelligentSuggestionSettings: () => getSettings(),
    getIntelligentSuggestionTemplates: () => getTemplates(),
    getIntelligentSuggestionRules: () => getRules(),
    updateIntelligentSuggestionSettings: vi.fn(),
    createIntelligentSuggestionRule: vi.fn(),
    updateIntelligentSuggestionRule: vi.fn(),
    deleteIntelligentSuggestionRule: vi.fn(),
}))

describe("IntelligentSuggestionsSection", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        getSettings.mockResolvedValue({
            enabled: true,
            new_unread_enabled: true,
            new_unread_business_days: 2,
            meeting_outcome_enabled: true,
            meeting_outcome_business_days: 1,
            stuck_enabled: true,
            stuck_business_days: 5,
            daily_digest_enabled: true,
            digest_hour_local: 9,
        })
        getTemplates.mockResolvedValue([
            {
                template_key: "new_unread_stale",
                name: "New unread follow-up",
                description: "Follow up on new unread records.",
                rule_kind: "stage_inactivity",
                default_stage_slug: "new_unread",
                default_stage_key: "new_unread",
                default_stage_label: "New Unread",
                default_business_days: 2,
                is_default: true,
            },
        ])
        getRules.mockResolvedValue([])
    })

    it("reuses fresh settings data when the section remounts", async () => {
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: {
                    retry: false,
                },
            },
        })
        const renderSection = () =>
            render(
                <QueryClientProvider client={queryClient}>
                    <IntelligentSuggestionsSection />
                </QueryClientProvider>,
            )

        const firstView = renderSection()
        expect(await screen.findByText("Enable Intelligent Suggestions")).toBeInTheDocument()
        firstView.unmount()

        renderSection()
        expect(await screen.findByText("Enable Intelligent Suggestions")).toBeInTheDocument()

        expect(getSettings).toHaveBeenCalledTimes(1)
        expect(getTemplates).toHaveBeenCalledTimes(1)
        expect(getRules).toHaveBeenCalledTimes(1)
    })
})
