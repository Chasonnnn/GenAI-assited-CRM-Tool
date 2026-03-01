import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"

const mockSendFormIntakeLink = vi.fn()
const mockUseFormIntakeLinks = vi.fn()
const mockUseSurrogateFormSubmission = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            org_portal_base_url: "https://portal.example.com",
        },
    }),
}))

vi.mock("@/lib/hooks/use-forms", () => ({
    useSurrogateFormSubmission: (...args: unknown[]) => mockUseSurrogateFormSubmission(...args),
    useSurrogateFormDraftStatus: () => ({ data: null }),
    useFormIntakeLinks: (...args: unknown[]) => mockUseFormIntakeLinks(...args),
    useSendFormIntakeLink: () => ({ mutateAsync: mockSendFormIntakeLink, isPending: false }),
    useApproveFormSubmission: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRejectFormSubmission: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateSubmissionAnswers: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUploadSubmissionFile: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteSubmissionFile: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: () => ({
        data: [{ id: "template-1", name: "Application Invite" }],
        isLoading: false,
    }),
}))

vi.mock("@/lib/api/forms", () => ({
    exportSubmissionPdf: vi.fn(),
    getSubmissionFileDownloadUrl: vi.fn(),
}))

describe("SurrogateApplicationTab", () => {
    beforeEach(() => {
        mockSendFormIntakeLink.mockReset()
        mockUseFormIntakeLinks.mockReset()
        mockUseSurrogateFormSubmission.mockReset()
        mockUseSurrogateFormSubmission.mockReturnValue({
            data: null,
            isLoading: false,
            error: null,
        })
        mockUseFormIntakeLinks.mockReturnValue({
            data: [
                {
                    id: "link-1",
                    form_id: "form-1",
                    slug: "shared-slug",
                    campaign_name: "Default Shared Link",
                    event_name: null,
                    utm_defaults: null,
                    is_active: true,
                    expires_at: null,
                    max_submissions: null,
                    submissions_count: 0,
                    intake_url: "https://portal.example.com/intake/shared-slug",
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
            error: null,
        })
    })

    it("uses shared intake link send flow", async () => {
        mockSendFormIntakeLink.mockResolvedValue({
            intake_link_id: "link-1",
            template_id: "template-1",
            email_log_id: "email-log-1",
            sent_at: new Date().toISOString(),
            intake_url: "https://portal.example.com/intake/shared-slug",
        })

        render(
            <SurrogateApplicationTab
                surrogateId="surrogate-1"
                formId="form-1"
                publishedForms={[
                    {
                        id: "form-1",
                        name: "Application Form",
                        status: "published",
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                    },
                ]}
            />,
        )

        fireEvent.click(screen.getByRole("button", { name: /send form link/i }))

        expect(await screen.findByText(/portal\.example\.com\/intake\/shared-slug/i)).toBeInTheDocument()

        await waitFor(() =>
            expect(screen.getByRole("button", { name: /send email/i })).toBeEnabled(),
        )
        fireEvent.click(screen.getByRole("button", { name: /send email/i }))

        await waitFor(() =>
            expect(mockSendFormIntakeLink).toHaveBeenCalledWith({
                formId: "form-1",
                linkId: "link-1",
                surrogateId: "surrogate-1",
                templateId: "template-1",
            }),
        )
    })

    it("shows a persistent field-selection hint before file upload when multiple file fields exist", async () => {
        mockUseSurrogateFormSubmission.mockReturnValue({
            isLoading: false,
            error: null,
            data: {
                id: "submission-1",
                form_id: "form-1",
                surrogate_id: "surrogate-1",
                status: "pending_review",
                submitted_at: new Date().toISOString(),
                reviewed_at: null,
                reviewed_by_user_id: null,
                review_notes: null,
                source_mode: "dedicated",
                intake_link_id: null,
                intake_lead_id: null,
                match_status: "linked",
                match_reason: "dedicated_token",
                matched_at: new Date().toISOString(),
                answers: {},
                schema_snapshot: {
                    pages: [
                        {
                            title: "Uploads",
                            fields: [
                                {
                                    key: "id_docs",
                                    label: "ID Documents",
                                    type: "file",
                                    required: false,
                                },
                                {
                                    key: "insurance_docs",
                                    label: "Insurance Documents",
                                    type: "file",
                                    required: false,
                                },
                            ],
                        },
                    ],
                },
                files: [],
            },
        })

        render(
            <SurrogateApplicationTab
                surrogateId="surrogate-1"
                formId="form-1"
                publishedForms={[]}
            />,
        )

        fireEvent.click(screen.getByRole("button", { name: /edit/i }))

        expect(
            await screen.findByText(/choose a file field to enable upload/i),
        ).toBeInTheDocument()
    })
})
