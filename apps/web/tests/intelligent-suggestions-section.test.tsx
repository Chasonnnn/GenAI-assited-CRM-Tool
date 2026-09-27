import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { IntelligentSuggestionsSection } from "../app/(app)/settings/intelligent-suggestions-section"

vi.unmock("@tanstack/react-query")

const getSettings = vi.fn()
const getTemplates = vi.fn()
const getRules = vi.fn()
const updateSettings = vi.fn()
const createRule = vi.fn()
const deleteRule = vi.fn()

const DEFAULT_STAGES = [
    { slug: "new_unread", stage_key: "new_unread", label: "New Unread", is_active: true, order: 1 },
]
let mockStages: Array<Record<string, unknown>> = DEFAULT_STAGES

vi.mock("@/lib/hooks/use-pipelines", () => ({
    usePipelines: () => ({ data: [{ stages: mockStages }] }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/api/settings", () => ({
    getIntelligentSuggestionSettings: () => getSettings(),
    getIntelligentSuggestionTemplates: () => getTemplates(),
    getIntelligentSuggestionRules: () => getRules(),
    updateIntelligentSuggestionSettings: (payload: unknown) => updateSettings(payload),
    createIntelligentSuggestionRule: (payload: unknown) => createRule(payload),
    updateIntelligentSuggestionRule: vi.fn(),
    deleteIntelligentSuggestionRule: (ruleId: string) => deleteRule(ruleId),
}))

const SETTINGS = {
    enabled: true,
    new_unread_enabled: true,
    new_unread_business_days: 2,
    meeting_outcome_enabled: true,
    meeting_outcome_business_days: 1,
    stuck_enabled: true,
    stuck_business_days: 5,
    daily_digest_enabled: true,
    digest_hour_local: 9,
}

const EXISTING_RULE = {
    id: "rule-1",
    organization_id: "org-1",
    template_key: "new_unread_stale",
    name: "Stale new leads",
    rule_kind: "stage_inactivity",
    stage_slug: "new_unread",
    stage_key: "new_unread",
    stage_label: "New Unread",
    business_days: 2,
    enabled: true,
    sort_order: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
}

function renderSection() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
        <QueryClientProvider client={queryClient}>
            <IntelligentSuggestionsSection />
        </QueryClientProvider>,
    )
}

describe("IntelligentSuggestionsSection", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockStages = DEFAULT_STAGES
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

    it("lists stages in pipeline order, not alphabetically", async () => {
        mockStages = [
            { slug: "approved", stage_key: "approved", label: "Approved", is_active: true, order: 3 },
            { slug: "new_unread", stage_key: "new_unread", label: "New Unread", is_active: true, order: 1 },
            { slug: "contacted", stage_key: "contacted", label: "Contacted", is_active: true, order: 2 },
        ]
        renderSection()

        fireEvent.click(await screen.findByRole("combobox", { name: "Stage" }))
        const options = await screen.findAllByRole("option")
        expect(options.map((option) => option.textContent)).toEqual(["New Unread", "Contacted", "Approved"])
    })

    it("blocks adding a rule that duplicates an existing one", async () => {
        getRules.mockResolvedValue([EXISTING_RULE])
        renderSection()

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "A rule with this template, stage and threshold already exists.",
        )
        expect(screen.getByRole("button", { name: "Add Rule" })).toBeDisabled()

        fireEvent.change(screen.getByLabelText("Business days"), { target: { value: "3" } })
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Add Rule" })).toBeEnabled()
    })

    it("saves the global toggle immediately and has no separate save button", async () => {
        updateSettings.mockResolvedValue({ ...SETTINGS, enabled: false })
        renderSection()

        const toggle = await screen.findByRole("switch", { name: "Enable Intelligent Suggestions" })
        expect(screen.queryByRole("button", { name: /save intelligent suggestion rules/i })).not.toBeInTheDocument()

        fireEvent.click(toggle)

        await waitFor(() => expect(updateSettings).toHaveBeenCalledWith({ enabled: false }))
    })

    it("shows the digest hour as a time", async () => {
        renderSection()

        expect(await screen.findByRole("combobox", { name: /digest hour/i })).toHaveTextContent("9:00 AM")
    })

    it("lists rules in a table and deletes through a confirm dialog", async () => {
        const confirmSpy = vi.spyOn(window, "confirm")
        getRules.mockResolvedValue([EXISTING_RULE])
        deleteRule.mockResolvedValue(undefined)
        renderSection()

        const row = (await screen.findByRole("cell", { name: "Stale new leads" })).closest("tr")
        expect(row).not.toBeNull()
        expect(within(row as HTMLElement).getByRole("cell", { name: "New Unread" })).toBeInTheDocument()
        expect(within(row as HTMLElement).getByRole("cell", { name: "New unread follow-up" })).toBeInTheDocument()

        fireEvent.click(within(row as HTMLElement).getByRole("button", { name: "Actions for Stale new leads" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))

        const dialog = await screen.findByRole("alertdialog")
        expect(within(dialog).getByText("Delete Stale new leads?")).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole("button", { name: "Delete rule" }))

        await waitFor(() => expect(deleteRule).toHaveBeenCalledWith("rule-1"))
        await waitFor(() => expect(screen.queryByRole("cell", { name: "Stale new leads" })).not.toBeInTheDocument())
        expect(confirmSpy).not.toHaveBeenCalled()
        confirmSpy.mockRestore()
    })
})
