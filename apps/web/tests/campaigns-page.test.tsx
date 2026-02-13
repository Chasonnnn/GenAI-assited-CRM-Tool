import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import CampaignsPage from "../app/(app)/automation/campaigns/page"

const mockPush = vi.fn()

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
    useCampaigns: () => ({
        data: [
            {
                id: "camp1",
                name: "Test Campaign 1",
                description: null,
                email_template_id: "tmpl1",
                email_template_name: "Template 1",
                recipient_type: "case",
                filter_criteria: {},
                scheduled_at: null,
                status: "draft",
                created_by_user_id: null,
                created_by_name: null,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                total_recipients: 10,
                sent_count: 0,
                failed_count: 0,
                skipped_count: 0,
                opened_count: 0,
                clicked_count: 0,
            }
        ],
        isLoading: false,
    }),
    useCreateCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDuplicateCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCancelCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSendCampaign: () => ({ mutateAsync: vi.fn(), isPending: false }),
    usePreviewFilters: () => ({
        data: { total_count: 0, sample_recipients: [] },
        isLoading: false,
        refetch: vi.fn(),
        mutate: vi.fn(),
    }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplate: () => ({ data: { subject: "Hello", body: "Body" } }),
    useEmailTemplates: () => ({ data: [] }),
}))

vi.mock("@tanstack/react-query", () => ({
    useQuery: () => ({ data: { stages: [] } }), // For defaultPipeline
    useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))

describe("CampaignsPage", () => {
    it("renders campaign list with accessible action buttons", async () => {
        render(<CampaignsPage />)

        // Ensure the campaign is rendered
        expect(screen.getByText("Test Campaign 1")).toBeInTheDocument()

        // Check for the accessible action button
        // This should initially fail because the aria-label is missing
        const actionButton = screen.getByRole("button", { name: "Actions for Test Campaign 1" })
        expect(actionButton).toBeInTheDocument()
    })
})
