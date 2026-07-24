import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"

const mockSendFormIntakeLink = vi.fn()
const mockUseFormIntakeLinks = vi.fn()
const mockUseSurrogateFormSubmission = vi.fn()
const mockUseEmailTemplates = vi.fn()
const FIXED_TIMESTAMP = "2026-01-01T00:00:00.000Z"

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
    useEmailTemplates: () => mockUseEmailTemplates(),
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
        mockUseEmailTemplates.mockReset()
        mockUseEmailTemplates.mockReturnValue({
            data: [
                { id: "template-1", name: "Application Invite" },
                { id: "template-2", name: "Application Reminder" },
            ],
            isLoading: false,
        })
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
                    created_at: FIXED_TIMESTAMP,
                    updated_at: FIXED_TIMESTAMP,
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
            queued_at: FIXED_TIMESTAMP,
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
                        created_at: FIXED_TIMESTAMP,
                        updated_at: FIXED_TIMESTAMP,
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
                idempotencyKey: expect.any(String),
            }),
        )
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    })

    it("reuses the intake-link occurrence id when a queued request is retried", async () => {
        mockSendFormIntakeLink
            .mockRejectedValueOnce(new Error("temporary failure"))
            .mockResolvedValueOnce({
                intake_link_id: "link-1",
                template_id: "template-1",
                email_log_id: "email-log-1",
                queued_at: FIXED_TIMESTAMP,
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
                        created_at: FIXED_TIMESTAMP,
                        updated_at: FIXED_TIMESTAMP,
                    },
                ]}
            />,
        )

        fireEvent.click(screen.getByRole("button", { name: /send form link/i }))
        const sendButton = await screen.findByRole("button", { name: /^send email$/i })
        fireEvent.click(sendButton)
        await waitFor(() => expect(mockSendFormIntakeLink).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(sendButton).toBeEnabled())

        fireEvent.click(sendButton)
        await waitFor(() => expect(mockSendFormIntakeLink).toHaveBeenCalledTimes(2))

        const firstOccurrenceId = mockSendFormIntakeLink.mock.calls[0]?.[0]?.idempotencyKey
        const secondOccurrenceId = mockSendFormIntakeLink.mock.calls[1]?.[0]?.idempotencyKey
        expect(firstOccurrenceId).toEqual(expect.any(String))
        expect(secondOccurrenceId).toBe(firstOccurrenceId)
    })

    it("regenerates the occurrence when the modal template or shared link changes", async () => {
        mockUseFormIntakeLinks.mockReturnValue({
            data: [
                {
                    id: "link-1",
                    form_id: "form-1",
                    slug: "shared-slug",
                    campaign_name: "Default Shared Link",
                    event_name: null,
                    is_active: true,
                    intake_url: "https://portal.example.com/intake/shared-slug",
                    created_at: FIXED_TIMESTAMP,
                    updated_at: FIXED_TIMESTAMP,
                },
                {
                    id: "link-2",
                    form_id: "form-1",
                    slug: "reminder-link",
                    campaign_name: "Reminder Link",
                    event_name: null,
                    is_active: true,
                    intake_url: "https://portal.example.com/intake/reminder-link",
                    created_at: FIXED_TIMESTAMP,
                    updated_at: FIXED_TIMESTAMP,
                },
            ],
            isLoading: false,
            error: null,
        })
        mockSendFormIntakeLink
            .mockRejectedValueOnce(new Error("temporary failure"))
            .mockRejectedValueOnce(new Error("temporary failure"))
            .mockResolvedValueOnce({
                intake_link_id: "link-2",
                template_id: "template-2",
                email_log_id: "email-log-2",
                queued_at: FIXED_TIMESTAMP,
                intake_url: "https://portal.example.com/intake/reminder-link",
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
                        created_at: FIXED_TIMESTAMP,
                        updated_at: FIXED_TIMESTAMP,
                    },
                ]}
            />,
        )

        fireEvent.click(screen.getByRole("button", { name: /send form link/i }))
        const sendButton = await screen.findByRole("button", { name: /^send email$/i })
        fireEvent.click(sendButton)
        await waitFor(() => expect(mockSendFormIntakeLink).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(sendButton).toBeEnabled())

        const templateSelect = screen.getByRole("combobox", { name: /email template/i })
        fireEvent.click(templateSelect)
        const templateOption = await screen.findByRole("option", {
            name: "Application Reminder",
        })
        fireEvent.mouseMove(templateOption)
        fireEvent.click(templateOption)
        fireEvent.click(sendButton)
        await waitFor(() => expect(mockSendFormIntakeLink).toHaveBeenCalledTimes(2))
        await waitFor(() => expect(sendButton).toBeEnabled())

        const linkSelect = screen.getByRole("combobox", { name: /shared intake link/i })
        fireEvent.click(linkSelect)
        const linkOption = await screen.findByRole("option", { name: "Reminder Link" })
        fireEvent.mouseMove(linkOption)
        fireEvent.click(linkOption)
        fireEvent.click(sendButton)
        await waitFor(() => expect(mockSendFormIntakeLink).toHaveBeenCalledTimes(3))

        const firstCall = mockSendFormIntakeLink.mock.calls[0][0]
        const templateChangedCall = mockSendFormIntakeLink.mock.calls[1][0]
        const linkChangedCall = mockSendFormIntakeLink.mock.calls[2][0]
        expect(templateChangedCall.idempotencyKey).not.toBe(firstCall.idempotencyKey)
        expect(templateChangedCall.templateId).toBe("template-2")
        expect(linkChangedCall.idempotencyKey).not.toBe(templateChangedCall.idempotencyKey)
        expect(linkChangedCall.linkId).toBe("link-2")
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    })

    it("uses shadcn selects for shared intake link and email template pickers", async () => {
        render(
            <SurrogateApplicationTab
                surrogateId="surrogate-1"
                formId="form-1"
                publishedForms={[
                    {
                        id: "form-1",
                        name: "Application Form",
                        status: "published",
                        created_at: FIXED_TIMESTAMP,
                        updated_at: FIXED_TIMESTAMP,
                    },
                ]}
            />,
        )

        expect(
            screen.getByRole("combobox", { name: /shared intake link/i }),
        ).toHaveAttribute("data-slot", "select-trigger")

        fireEvent.click(screen.getByRole("button", { name: /send form link/i }))

        expect(
            await screen.findByRole("combobox", { name: /email template/i }),
        ).toHaveAttribute("data-slot", "select-trigger")
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
                submitted_at: FIXED_TIMESTAMP,
                reviewed_at: null,
                reviewed_by_user_id: null,
                review_notes: null,
                source_mode: "shared",
                intake_link_id: null,
                intake_lead_id: null,
                match_status: "linked",
                match_reason: "manual_match",
                matched_at: FIXED_TIMESTAMP,
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

    it("adds contextual aria-labels to field and file icon actions", async () => {
        mockUseSurrogateFormSubmission.mockReturnValue({
            isLoading: false,
            error: null,
            data: {
                id: "submission-2",
                form_id: "form-1",
                surrogate_id: "surrogate-1",
                status: "pending_review",
                submitted_at: FIXED_TIMESTAMP,
                reviewed_at: null,
                reviewed_by_user_id: null,
                review_notes: null,
                source_mode: "shared",
                intake_link_id: null,
                intake_lead_id: null,
                match_status: "linked",
                match_reason: "manual_match",
                matched_at: FIXED_TIMESTAMP,
                answers: {
                    email: "surrogate@example.com",
                },
                schema_snapshot: {
                    pages: [
                        {
                            title: "Info",
                            fields: [
                                {
                                    key: "email",
                                    label: "Email",
                                    type: "email",
                                    required: false,
                                },
                                {
                                    key: "documents",
                                    label: "Documents",
                                    type: "file",
                                    required: false,
                                },
                            ],
                        },
                    ],
                },
                files: [
                    {
                        id: "file-1",
                        filename: "medical-records.pdf",
                        field_key: "documents",
                        file_size: 1024,
                        quarantined: false,
                    },
                ],
            },
        })

        render(
            <SurrogateApplicationTab
                surrogateId="surrogate-1"
                formId="form-1"
                publishedForms={[]}
            />,
        )

        expect(
            screen.getByRole("button", { name: "Download medical-records.pdf" }),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /^edit$/i }))

        const editFieldButton = await screen.findByRole("button", { name: "Edit Email" })
        expect(editFieldButton).toBeInTheDocument()

        fireEvent.click(editFieldButton)

        expect(
            screen.getByRole("button", { name: "Cancel editing Email" }),
        ).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: "Delete medical-records.pdf" }),
        ).toBeInTheDocument()
    })

    it("renders option labels instead of stored slugs for journey timing answers", () => {
        mockUseSurrogateFormSubmission.mockReturnValue({
            isLoading: false,
            error: null,
            data: {
                id: "submission-3",
                form_id: "form-1",
                surrogate_id: "surrogate-1",
                status: "pending_review",
                submitted_at: FIXED_TIMESTAMP,
                reviewed_at: null,
                reviewed_by_user_id: null,
                review_notes: null,
                source_mode: "shared",
                intake_link_id: null,
                intake_lead_id: null,
                match_status: "linked",
                match_reason: "manual_match",
                matched_at: FIXED_TIMESTAMP,
                answers: {
                    journey_timing_preference: "months_0_3",
                },
                schema_snapshot: {
                    pages: [
                        {
                            title: "Timing",
                            fields: [
                                {
                                    key: "journey_timing_preference",
                                    label: "When would you like to start your surrogacy journey?",
                                    type: "radio",
                                    required: false,
                                    options: [
                                        { label: "0–3 months", value: "months_0_3" },
                                        { label: "3–6 months", value: "months_3_6" },
                                        { label: "Still deciding", value: "still_deciding" },
                                    ],
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

        expect(screen.getByText("0–3 months")).toBeInTheDocument()
        expect(screen.queryByText("months_0_3")).not.toBeInTheDocument()
    })

    it("uses shadcn selects when editing single-choice application answers", async () => {
        mockUseSurrogateFormSubmission.mockReturnValue({
            isLoading: false,
            error: null,
            data: {
                id: "submission-4",
                form_id: "form-1",
                surrogate_id: "surrogate-1",
                status: "pending_review",
                submitted_at: FIXED_TIMESTAMP,
                reviewed_at: null,
                reviewed_by_user_id: null,
                review_notes: null,
                source_mode: "shared",
                intake_link_id: null,
                intake_lead_id: null,
                match_status: "linked",
                match_reason: "manual_match",
                matched_at: FIXED_TIMESTAMP,
                answers: {
                    journey_timing_preference: "months_0_3",
                },
                schema_snapshot: {
                    pages: [
                        {
                            title: "Timing",
                            fields: [
                                {
                                    key: "journey_timing_preference",
                                    label: "Journey Timing",
                                    type: "radio",
                                    required: false,
                                    options: [
                                        { label: "0–3 months", value: "months_0_3" },
                                        { label: "3–6 months", value: "months_3_6" },
                                        { label: "Still deciding", value: "still_deciding" },
                                    ],
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

        fireEvent.click(screen.getByRole("button", { name: /^edit$/i }))
        fireEvent.click(await screen.findByRole("button", { name: "Edit Journey Timing" }))

        expect(
            await screen.findByRole("combobox", { name: "Journey Timing" }),
        ).toHaveAttribute("data-slot", "select-trigger")
    })
})
