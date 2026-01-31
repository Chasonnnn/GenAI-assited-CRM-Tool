import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import CampaignDetailPage from "../app/(app)/automation/campaigns/[id]/page"

const mockPush = vi.fn()
const mockUseRunRecipients = vi.fn()

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
        data: {
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
        },
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
    useUpdateCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRetryFailedCampaignRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplate: () => ({ data: { subject: "Hello", body: "Body" } }),
    useEmailTemplates: () => ({ data: [] }),
}))

describe("CampaignDetailPage", () => {
    beforeEach(() => {
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
})
