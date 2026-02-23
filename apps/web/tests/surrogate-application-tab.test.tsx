import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"

const mockCreateFormToken = vi.fn()
const mockSendFormToken = vi.fn()
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
    useCreateFormToken: () => ({ mutateAsync: mockCreateFormToken, isPending: false }),
    useSendFormToken: () => ({ mutateAsync: mockSendFormToken, isPending: false }),
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
        mockCreateFormToken.mockReset()
        mockSendFormToken.mockReset()
        mockUseSurrogateFormSubmission.mockReset()
        mockUseSurrogateFormSubmission.mockReturnValue({
            data: null,
            isLoading: false,
            error: null,
        })
    })

    it("uses selected link expiration days when generating a link", async () => {
        mockCreateFormToken.mockResolvedValue({
            token_id: "token-id-123",
            token: "token-123",
            expires_at: "2026-04-15T13:00:00Z",
            application_url: "https://portal.example.com/apply/token-123",
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

        fireEvent.change(screen.getByLabelText(/link expiration/i), {
            target: { value: "30" },
        })
        fireEvent.click(screen.getByRole("button", { name: /send form link/i }))

        await waitFor(() =>
            expect(mockCreateFormToken).toHaveBeenCalledWith({
                formId: "form-1",
                surrogateId: "surrogate-1",
                expiresInDays: 30,
                allowPurposeOverride: false,
            }),
        )

        expect(await screen.findByText(/portal\.example\.com\/apply\/token-123/i)).toBeInTheDocument()
        expect(screen.getByText(/expires on/i)).toBeInTheDocument()
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
