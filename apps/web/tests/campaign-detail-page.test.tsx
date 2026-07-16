import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import CampaignDetailPage from "../app/(app)/automation/campaigns/[id]/page.client"

const mockPush = vi.fn()
const mockUseRunRecipients = vi.fn()
const mockUpdateCampaign = vi.fn()
let mockCampaignData = {
    id: "camp1",
    name: "Test Campaign",
    description: null as string | null,
    email_template_id: "tmpl1",
    recipient_type: "case",
    filter_criteria: {} as Record<string, unknown>,
    scheduled_at: null as string | null,
    status: "completed",
    created_by_user_id: null,
    created_by_name: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    total_recipients: 10,
    sent_count: 8,
    failed_count: 2,
    skipped_count: 0,
    opened_count: 0,
    clicked_count: 0,
}

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "camp1" }),
    useRouter: () => ({ push: mockPush }),
    useSearchParams: () => new URLSearchParams(),
}))

vi.mock("@/lib/hooks/use-campaigns", () => ({
    useCampaign: () => ({
        data: mockCampaignData,
        isLoading: false,
    }),
    useCampaignRuns: () => ({
        data: [
            {
                id: "run1",
                campaign_id: "camp1",
                started_at: new Date().toISOString(),
                completed_at: null,
                status: "failed",
                error_message: null,
                total_count: 10,
                sent_count: 8,
                failed_count: 2,
                skipped_count: 0,
                opened_count: 0,
                clicked_count: 0,
            },
        ],
    }),
    useCampaignPreview: () => ({
        data: { total_count: 0, sample_recipients: [] },
        isLoading: false,
        refetch: vi.fn(),
    }),
    useRunRecipients: (campaignId: string, runId: string, params?: { status?: string; limit?: number }) =>
        mockUseRunRecipients(campaignId, runId, params),
    useDeleteCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDuplicateCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCancelCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSendCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateCampaign: () => ({ mutateAsync: mockUpdateCampaign, isPending: false }),
    useRetryFailedCampaignRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplate: () => ({ data: { subject: "Hello", body: "Body" } }),
    useEmailTemplates: () => ({
        data: [
            { id: "tmpl1", name: "Original Template" },
            { id: "tmpl2", name: "Updated Template" },
        ],
    }),
}))

vi.mock("@/lib/hooks/use-metadata", () => ({
    useIntendedParentStatuses: () => ({
        data: {
            statuses: [
                {
                    id: "stage-new",
                    value: "new",
                    label: "New",
                    stage_key: "new",
                    stage_slug: "new",
                    stage_type: "intake",
                    color: "#3B82F6",
                    order: 1,
                },
            ],
        },
    }),
}))

describe("CampaignDetailPage", () => {
    beforeEach(() => {
        mockCampaignData = {
            id: "camp1",
            name: "Test Campaign",
            description: null,
            email_template_id: "tmpl1",
            recipient_type: "case",
            filter_criteria: {},
            scheduled_at: null,
            status: "completed",
            created_by_user_id: null,
            created_by_name: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            total_recipients: 10,
            sent_count: 8,
            failed_count: 2,
            skipped_count: 0,
            opened_count: 0,
            clicked_count: 0,
        }
        mockUpdateCampaign.mockReset()
        mockUpdateCampaign.mockResolvedValue({})
        mockUseRunRecipients.mockReturnValue({ data: [] })
    })

    it("shows Failed tab and requests failed recipients on selection", async () => {
        render(<CampaignDetailPage />)

        expect(screen.getByRole("tab", { name: /Failed/i })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("tab", { name: /Failed/i }))

        await waitFor(() => {
            expect(mockUseRunRecipients).toHaveBeenLastCalledWith(
                "camp1",
                "run1",
                expect.objectContaining({ status: "failed" })
            )
        })
    })

    it("saves edits using the current campaign draft", async () => {
        mockCampaignData = {
            ...mockCampaignData,
            name: "Draft Campaign",
            description: "Existing description",
            status: "draft",
            filter_criteria: {
                stage_ids: ["stage-new"],
                states: ["CA"],
            },
            include_unsubscribed: false,
        }

        render(<CampaignDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: /^edit$/i }))

        expect(screen.getByLabelText(/campaign name/i)).toHaveValue("Draft Campaign")
        expect(screen.getByLabelText(/description/i)).toHaveValue("Existing description")

        fireEvent.change(screen.getByLabelText(/campaign name/i), {
            target: { value: "Updated Campaign" },
        })
        fireEvent.change(screen.getByLabelText(/description/i), {
            target: { value: "Updated description" },
        })
        fireEvent.click(screen.getByRole("checkbox", { name: /include unsubscribed recipients/i }))

        fireEvent.click(screen.getByRole("button", { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdateCampaign).toHaveBeenCalledWith({
                id: "camp1",
                data: {
                    name: "Updated Campaign",
                    description: "Updated description",
                    email_template_id: "tmpl1",
                    recipient_type: "case",
                    filter_criteria: {
                        stage_ids: ["stage-new"],
                        states: ["CA"],
                    },
                    include_unsubscribed: true,
                },
            })
        })
    })

    it("preserves an in-progress campaign edit when equivalent campaign data rerenders", () => {
        mockCampaignData = {
            ...mockCampaignData,
            status: "draft",
        }

        const { rerender } = render(<CampaignDetailPage />)
        fireEvent.click(screen.getByRole("button", { name: /^edit$/i }))
        fireEvent.change(screen.getByLabelText(/campaign name/i), {
            target: { value: "Unsaved campaign name" },
        })

        mockCampaignData = { ...mockCampaignData }
        rerender(<CampaignDetailPage />)

        expect(screen.getByLabelText(/campaign name/i)).toHaveValue("Unsaved campaign name")
    })
})
