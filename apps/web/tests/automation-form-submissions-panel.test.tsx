import { beforeEach, describe, expect, it, vi } from "vitest"
import type { ComponentProps } from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

const {
    getSubmissionFileDownloadUrlMock,
    listSubmissionDonorCandidatesMock,
    resolveSubmissionMatchMock,
    approveSubmissionMock,
    rejectSubmissionMock,
    rescanSubmissionFileMock,
    listDonorsMock,
    toastMock,
} = vi.hoisted(() => ({
    getSubmissionFileDownloadUrlMock: vi.fn(),
    listSubmissionDonorCandidatesMock: vi.fn(),
    resolveSubmissionMatchMock: vi.fn(),
    approveSubmissionMock: vi.fn(),
    rejectSubmissionMock: vi.fn(),
    rescanSubmissionFileMock: vi.fn(),
    listDonorsMock: vi.fn(),
    toastMock: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/api/forms", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/forms")>("@/lib/api/forms")
    return {
        ...actual,
        getSubmissionFileDownloadUrl: getSubmissionFileDownloadUrlMock,
        listSubmissionDonorCandidates: listSubmissionDonorCandidatesMock,
        resolveSubmissionMatch: resolveSubmissionMatchMock,
        approveSubmission: approveSubmissionMock,
        rejectSubmission: rejectSubmissionMock,
        rescanSubmissionFile: rescanSubmissionFileMock,
    }
})

vi.mock("@/lib/api/donors", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/donors")>("@/lib/api/donors")
    return { ...actual, listDonors: listDonorsMock }
})

vi.mock("@/components/ui/toast", () => ({ toast: toastMock }))

import { AutomationFormSubmissionsPanel } from "@/components/forms/builder/AutomationFormSubmissionsPanel"
import type { FormSubmissionRead, MatchCandidateRead } from "@/lib/api/forms"

function makeSubmission(overrides: Partial<FormSubmissionRead>): FormSubmissionRead {
    return {
        id: "submission-1",
        form_id: "form-1",
        surrogate_id: null,
        donor_id: null,
        lead_kind: "surrogate",
        status: "pending_review",
        submitted_at: "2026-07-05T15:00:00Z",
        reviewed_at: null,
        reviewed_by_user_id: null,
        review_notes: null,
        answers: {
            full_name: "Alex Applicant",
            date_of_birth: "1992-04-13",
            phone: "555-0101",
            email: "alex@example.com",
        },
        schema_snapshot: null,
        source_mode: "shared",
        intake_link_id: "link-1",
        intake_lead_id: null,
        match_status: "ambiguous_review",
        match_reason: null,
        matched_at: null,
        files: [],
        ...overrides,
    }
}

describe("AutomationFormSubmissionsPanel", () => {
    it("preserves queue, history, and candidate review actions after section splits", () => {
        const ambiguousSubmission = makeSubmission({
            id: "sub-ambiguous",
        })
        const leadSubmission = makeSubmission({
            id: "sub-lead",
            intake_lead_id: "lead-1",
            match_status: "lead_created",
            answers: {
                full_name: "Lead Applicant",
                date_of_birth: "1991-01-11",
                phone: "555-0202",
                email: "lead@example.com",
            },
        })
        const historySubmission = makeSubmission({
            id: "sub-history",
            surrogate_id: "sur-1",
            intake_lead_id: "lead-2",
            answers: {
                full_name: "History Applicant",
                date_of_birth: "1990-09-09",
                phone: "555-0303",
                email: "history@example.com",
            },
        })
        const candidate: MatchCandidateRead = {
            id: "candidate-1",
            submission_id: "sub-ambiguous",
            surrogate_id: "sur-candidate",
            reason: "phone_dob_name_ambiguous",
            created_at: "2026-07-05T15:01:00Z",
        }
        const onOpenApprovalQueue = vi.fn()
        const onSubmissionHistoryFilterChange = vi.fn()
        const onSelectQueueSubmission = vi.fn()
        const onLinkByManualSurrogateId = vi.fn()
        const onResolveSubmissionToSurrogate = vi.fn()
        const onResolveSubmissionToLead = vi.fn()
        const onRetrySubmissionMatch = vi.fn()
        const onPromoteLeadFromSubmission = vi.fn()

        render(
            <AutomationFormSubmissionsPanel
                formId="form-1"
                pendingSubmissionHistory={[ambiguousSubmission]}
                processedSubmissionHistory={[historySubmission]}
                ambiguousSubmissions={[ambiguousSubmission]}
                leadQueueSubmissions={[leadSubmission]}
                visibleSubmissionHistory={[historySubmission]}
                submissionHistoryFilter="all"
                selectedQueueSubmissionId="sub-ambiguous"
                selectedMatchCandidates={[candidate]}
                isSubmissionHistoryLoading={false}
                isMatchCandidatesLoading={false}
                retrySubmissionMatchPending={false}
                resolveSubmissionMatchPending={false}
                promoteIntakeLeadPending={false}
                manualSurrogateId="manual-sur-1"
                resolveReviewNotes="Looks correct"
                readAnswerValue={(submission, keys) => {
                    const answers = submission.answers as Record<string, unknown>
                    const value = keys.map((key) => answers[key]).find(Boolean)
                    return typeof value === "string" ? value : "—"
                }}
                formatSubmissionDateTime={(isoString) => `formatted ${isoString}`}
                submissionOutcomeLabel={(submission) => submission.match_status}
                submissionOutcomeBadgeClass={() => "outcome-class"}
                submissionReviewLabel={(submission) => submission.status}
                submissionReviewBadgeClass={() => "review-class"}
                onOpenApprovalQueue={onOpenApprovalQueue}
                onSubmissionHistoryFilterChange={onSubmissionHistoryFilterChange}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onManualSurrogateIdChange={vi.fn()}
                onResolveReviewNotesChange={vi.fn()}
                onLinkByManualSurrogateId={onLinkByManualSurrogateId}
                onResolveSubmissionToSurrogate={onResolveSubmissionToSurrogate}
                onResolveSubmissionToLead={onResolveSubmissionToLead}
                onRetrySubmissionMatch={onRetrySubmissionMatch}
                onPromoteLeadFromSubmission={onPromoteLeadFromSubmission}
            />,
        )

        expect(screen.getByText("Pending Applications")).toBeInTheDocument()
        expect(screen.getByText("Ambiguous Match Queue")).toBeInTheDocument()
        expect(screen.getByText("Lead Promotion Queue")).toBeInTheDocument()
        expect(screen.getByText("Submission History")).toBeInTheDocument()
        expect(screen.getByLabelText("Reviewer notes")).toHaveValue("Looks correct")
        expect(screen.getByLabelText("Manual surrogate ID link")).toHaveValue("manual-sur-1")

        fireEvent.click(screen.getByRole("button", { name: "Open Approval Queue" }))
        expect(onOpenApprovalQueue).toHaveBeenCalledTimes(1)

        fireEvent.click(screen.getByRole("button", { name: "Hide Candidates" }))
        expect(onSelectQueueSubmission).toHaveBeenCalledWith(null)

        fireEvent.click(screen.getByRole("button", { name: "Keep As Lead" }))
        expect(onResolveSubmissionToLead).toHaveBeenCalledWith("sub-ambiguous")

        fireEvent.click(screen.getByRole("button", { name: "Promote Lead" }))
        expect(onPromoteLeadFromSubmission).toHaveBeenCalledWith(leadSubmission)

        fireEvent.click(screen.getByRole("button", { name: "Processed" }))
        expect(onSubmissionHistoryFilterChange).toHaveBeenCalledWith("processed")

        fireEvent.click(screen.getAllByRole("button", { name: "Review Candidates" })[0])
        expect(onSelectQueueSubmission).toHaveBeenCalledWith("sub-history")

        fireEvent.click(screen.getByRole("button", { name: "Re-run Auto-Match" }))
        expect(onRetrySubmissionMatch).toHaveBeenCalledWith(
            historySubmission,
            {
                unlinkSurrogate: true,
                rerunAutoMatch: true,
            },
            "Auto-match re-run complete",
        )

        fireEvent.click(screen.getByRole("button", { name: "Unlink" }))
        expect(onRetrySubmissionMatch).toHaveBeenCalledWith(
            historySubmission,
            {
                unlinkSurrogate: true,
                rerunAutoMatch: false,
            },
            "Submission unlinked. Select the correct surrogate.",
        )

        fireEvent.click(screen.getByRole("button", { name: "Undo Lead + Reprocess" }))
        expect(onRetrySubmissionMatch).toHaveBeenCalledWith(
            historySubmission,
            {
                unlinkSurrogate: true,
                unlinkIntakeLead: true,
                rerunAutoMatch: true,
                createIntakeLeadIfUnmatched: true,
            },
            "Lead link reset and submission reprocessed",
        )

        fireEvent.click(screen.getByRole("button", { name: "Link Surrogate ID" }))
        expect(onLinkByManualSurrogateId).toHaveBeenCalledTimes(1)

        expect(screen.getByText("Several records share name, date of birth and phone")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Link Candidate" }))
        expect(onResolveSubmissionToSurrogate).toHaveBeenCalledWith("sub-ambiguous", "sur-candidate")
    })

    it("routes donor review and retry actions through intake-lead behavior", () => {
        const donorSubmission = makeSubmission({
            id: "sub-donor-review",
            lead_kind: "sperm_donor",
            match_status: "ambiguous_review",
        })
        const onResolveSubmissionToLead = vi.fn()
        const onRetrySubmissionMatch = vi.fn()

        render(
            <AutomationFormSubmissionsPanel
                formId="form-1"
                pendingSubmissionHistory={[donorSubmission]}
                processedSubmissionHistory={[]}
                ambiguousSubmissions={[donorSubmission]}
                leadQueueSubmissions={[]}
                visibleSubmissionHistory={[donorSubmission]}
                submissionHistoryFilter="all"
                selectedQueueSubmissionId={null}
                selectedMatchCandidates={[]}
                isSubmissionHistoryLoading={false}
                isMatchCandidatesLoading={false}
                retrySubmissionMatchPending={false}
                resolveSubmissionMatchPending={false}
                promoteIntakeLeadPending={false}
                manualSurrogateId=""
                resolveReviewNotes=""
                readAnswerValue={(submission, keys) => {
                    const answers = submission.answers as Record<string, unknown>
                    const value = keys.map((key) => answers[key]).find(Boolean)
                    return typeof value === "string" ? value : "—"
                }}
                formatSubmissionDateTime={(isoString) => isoString}
                submissionOutcomeLabel={() => "Needs Review"}
                submissionOutcomeBadgeClass={() => "outcome-class"}
                submissionReviewLabel={() => "Pending Review"}
                submissionReviewBadgeClass={() => "review-class"}
                onOpenApprovalQueue={vi.fn()}
                onSubmissionHistoryFilterChange={vi.fn()}
                onSelectQueueSubmission={vi.fn()}
                onManualSurrogateIdChange={vi.fn()}
                onResolveReviewNotesChange={vi.fn()}
                onLinkByManualSurrogateId={vi.fn()}
                onResolveSubmissionToSurrogate={vi.fn()}
                onResolveSubmissionToLead={onResolveSubmissionToLead}
                onRetrySubmissionMatch={onRetrySubmissionMatch}
                onPromoteLeadFromSubmission={vi.fn()}
            />,
        )

        fireEvent.click(screen.getByRole("button", { name: "Create Intake Lead" }))
        expect(onResolveSubmissionToLead).toHaveBeenCalledWith("sub-donor-review")

        fireEvent.click(screen.getByRole("button", { name: "Reprocess" }))
        expect(onRetrySubmissionMatch).toHaveBeenCalledWith(
            donorSubmission,
            {
                unlinkSurrogate: false,
                rerunAutoMatch: true,
                createIntakeLeadIfUnmatched: true,
            },
            "Submission reprocessed",
        )
        expect(screen.queryByRole("button", { name: "Review Candidates" })).not.toBeInTheDocument()
    })

    it("labels donor review records, previews only a clean image, and links the converted donor", async () => {
        getSubmissionFileDownloadUrlMock.mockResolvedValue({
            download_url: "https://files.example.test/profile.jpg",
            filename: "profile.jpg",
        })
        const donorSubmission = makeSubmission({
            id: "sub-donor",
            lead_kind: "egg_donor",
            donor_id: "donor-1",
            donor_number: "D10001",
            surrogate_id: null,
            match_status: "linked",
            answers: {
                full_name: "Alex Donor",
                email: "alex@example.com",
                phone: "555-0101",
                state: "New York",
                education: "Bachelor's degree",
            },
            files: [
                {
                    id: "photo-1",
                    filename: "profile.jpg",
                    content_type: "image/jpeg",
                    file_size: 1200,
                    quarantined: false,
                    scan_status: "clean",
                    field_key: "profile_photo",
                },
                {
                    id: "photo-pending",
                    filename: "pending.jpg",
                    content_type: "image/jpeg",
                    file_size: 1300,
                    quarantined: true,
                    scan_status: "pending",
                    field_key: "profile_photo",
                },
            ],
        })

        render(
            <AutomationFormSubmissionsPanel
                formId="form-1"
                pendingSubmissionHistory={[]}
                processedSubmissionHistory={[donorSubmission]}
                ambiguousSubmissions={[]}
                leadQueueSubmissions={[]}
                visibleSubmissionHistory={[donorSubmission]}
                submissionHistoryFilter="all"
                selectedQueueSubmissionId={null}
                selectedMatchCandidates={[]}
                isSubmissionHistoryLoading={false}
                isMatchCandidatesLoading={false}
                retrySubmissionMatchPending={false}
                resolveSubmissionMatchPending={false}
                promoteIntakeLeadPending={false}
                manualSurrogateId=""
                resolveReviewNotes=""
                readAnswerValue={(submission, keys) => {
                    const answers = submission.answers as Record<string, unknown>
                    const value = keys.map((key) => answers[key]).find(Boolean)
                    return typeof value === "string" ? value : "—"
                }}
                formatSubmissionDateTime={(isoString) => isoString}
                submissionOutcomeLabel={() => "Matched"}
                submissionOutcomeBadgeClass={() => "outcome-class"}
                submissionReviewLabel={() => "Pending Review"}
                submissionReviewBadgeClass={() => "review-class"}
                onOpenApprovalQueue={vi.fn()}
                onSubmissionHistoryFilterChange={vi.fn()}
                onSelectQueueSubmission={vi.fn()}
                onManualSurrogateIdChange={vi.fn()}
                onResolveReviewNotesChange={vi.fn()}
                onLinkByManualSurrogateId={vi.fn()}
                onResolveSubmissionToSurrogate={vi.fn()}
                onResolveSubmissionToLead={vi.fn()}
                onRetrySubmissionMatch={vi.fn()}
                onPromoteLeadFromSubmission={vi.fn()}
            />,
        )

        expect(screen.getByText("Egg Donor")).toBeInTheDocument()
        expect(screen.getByText("Bachelor's degree")).toBeInTheDocument()
        expect(screen.getByText("New York")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Open donor D10001" })).toHaveAttribute(
            "href",
            "/donors/donor-1",
        )
        expect(screen.getByText("D10001")).toBeInTheDocument()
        expect(await screen.findByRole("img", { name: "Egg donor profile photo" })).toHaveAttribute(
            "src",
            "https://files.example.test/profile.jpg",
        )
        expect(getSubmissionFileDownloadUrlMock).toHaveBeenCalledTimes(1)
        expect(getSubmissionFileDownloadUrlMock).toHaveBeenCalledWith("sub-donor", "photo-1")
        expect(screen.queryByRole("button", { name: "Re-run Auto-Match" })).not.toBeInTheDocument()
    })

    it("never exposes a raw donor UUID when the display number is unavailable", () => {
        const donorSubmission = makeSubmission({
            id: "sub-donor-missing",
            lead_kind: "sperm_donor",
            donor_id: "donor-internal-uuid",
            donor_number: null,
            surrogate_id: null,
            match_status: "linked",
            files: [],
        })

        render(
            <AutomationFormSubmissionsPanel
                formId="form-1"
                pendingSubmissionHistory={[]}
                processedSubmissionHistory={[donorSubmission]}
                ambiguousSubmissions={[]}
                leadQueueSubmissions={[]}
                visibleSubmissionHistory={[donorSubmission]}
                submissionHistoryFilter="all"
                selectedQueueSubmissionId={null}
                selectedMatchCandidates={[]}
                isSubmissionHistoryLoading={false}
                isMatchCandidatesLoading={false}
                retrySubmissionMatchPending={false}
                resolveSubmissionMatchPending={false}
                promoteIntakeLeadPending={false}
                manualSurrogateId=""
                resolveReviewNotes=""
                readAnswerValue={() => "—"}
                formatSubmissionDateTime={(isoString) => isoString}
                submissionOutcomeLabel={() => "Matched"}
                submissionOutcomeBadgeClass={() => "outcome-class"}
                submissionReviewLabel={() => "Pending Review"}
                submissionReviewBadgeClass={() => "review-class"}
                onOpenApprovalQueue={vi.fn()}
                onSubmissionHistoryFilterChange={vi.fn()}
                onSelectQueueSubmission={vi.fn()}
                onManualSurrogateIdChange={vi.fn()}
                onResolveReviewNotesChange={vi.fn()}
                onLinkByManualSurrogateId={vi.fn()}
                onResolveSubmissionToSurrogate={vi.fn()}
                onResolveSubmissionToLead={vi.fn()}
                onRetrySubmissionMatch={vi.fn()}
                onPromoteLeadFromSubmission={vi.fn()}
            />,
        )

        expect(screen.getByText("Donor record unavailable")).toBeInTheDocument()
        expect(screen.queryByText("donor-internal-uuid")).not.toBeInTheDocument()
        expect(screen.queryByRole("link", { name: /open donor/i })).not.toBeInTheDocument()
    })
})

type PanelProps = ComponentProps<typeof AutomationFormSubmissionsPanel>

function renderPanel(props: Partial<PanelProps>) {
    return render(
        <AutomationFormSubmissionsPanel
            formId="form-1"
            pendingSubmissionHistory={[]}
            processedSubmissionHistory={[]}
            ambiguousSubmissions={[]}
            leadQueueSubmissions={[]}
            visibleSubmissionHistory={[]}
            submissionHistoryFilter="all"
            selectedQueueSubmissionId={null}
            selectedMatchCandidates={[]}
            isSubmissionHistoryLoading={false}
            isMatchCandidatesLoading={false}
            retrySubmissionMatchPending={false}
            resolveSubmissionMatchPending={false}
            promoteIntakeLeadPending={false}
            manualSurrogateId=""
            resolveReviewNotes=""
            readAnswerValue={(submission, keys) => {
                const answers = submission.answers as Record<string, unknown>
                const value = keys.map((key) => answers[key]).find(Boolean)
                return typeof value === "string" ? value : "—"
            }}
            formatSubmissionDateTime={(isoString) => isoString}
            submissionOutcomeLabel={() => "Pending Match"}
            submissionOutcomeBadgeClass={() => "outcome-class"}
            submissionReviewLabel={() => "Pending Review"}
            submissionReviewBadgeClass={() => "review-class"}
            onOpenApprovalQueue={vi.fn()}
            onSubmissionHistoryFilterChange={vi.fn()}
            onSelectQueueSubmission={vi.fn()}
            onManualSurrogateIdChange={vi.fn()}
            onResolveReviewNotesChange={vi.fn()}
            onLinkByManualSurrogateId={vi.fn()}
            onResolveSubmissionToSurrogate={vi.fn()}
            onResolveSubmissionToLead={vi.fn()}
            onRetrySubmissionMatch={vi.fn()}
            onPromoteLeadFromSubmission={vi.fn()}
            {...props}
        />,
    )
}

function donorRecord(id: string, donorNumber: string, fullName: string) {
    return {
        id,
        donor_number: donorNumber,
        donor_type: "egg" as const,
        full_name: fullName,
        email: "",
        phone: null,
        state: null,
        education: null,
        source: null,
        owner_type: null,
        owner_id: null,
        stage_id: "stage-1",
        stage_key: "new",
        stage_slug: "new",
        status: "new",
        status_label: "New",
        profile_photo_attachment_id: null,
        is_archived: false,
        archived_at: null,
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
    }
}

function scanFile(id: string, filename: string, scanStatus: "error" | "clean") {
    return {
        id,
        filename,
        content_type: "image/jpeg",
        file_size: 100,
        quarantined: scanStatus !== "clean",
        scan_status: scanStatus,
        field_key: "profile_photo",
    }
}

describe("AutomationFormSubmissionsPanel donor review", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        listSubmissionDonorCandidatesMock.mockResolvedValue([])
        listDonorsMock.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 10, pages: 0 })
    })

    it("links a held donor application to a matching or searched donor with readable reasons", async () => {
        const held = makeSubmission({
            id: "sub-donor-held",
            lead_kind: "egg_donor",
            match_status: "ambiguous_review",
            match_reason: "donor_identity_conflict",
        })
        listSubmissionDonorCandidatesMock.mockResolvedValue([
            {
                donor_id: "donor-7",
                donor_number: "D10007",
                full_name: "Casey Candidate",
                donor_type: "egg",
                reason: "donor_email_match",
            },
        ])
        listDonorsMock.mockResolvedValue({
            items: [
                donorRecord("donor-7", "D10007", "Casey Candidate"),
                donorRecord("donor-8", "D10008", "Riley Search"),
            ],
            total: 2,
            page: 1,
            per_page: 10,
            pages: 1,
        })
        resolveSubmissionMatchMock.mockResolvedValue({
            submission: { ...held, donor_id: "donor-7", match_status: "linked", status: "approved" },
            outcome: "linked",
            candidate_count: 0,
        })

        renderPanel({ ambiguousSubmissions: [held], canEditSubject: () => true })

        expect(screen.getByText("Email or phone belongs to a different donor")).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Link to Donor" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Link to Donor" }))

        const matches = await screen.findByRole("list", { name: "Matching donors" })
        expect(within(matches).getByText("D10007 · Casey Candidate")).toBeInTheDocument()
        expect(within(matches).getByText("Email matches")).toBeInTheDocument()
        expect(listSubmissionDonorCandidatesMock).toHaveBeenCalledWith("sub-donor-held")

        fireEvent.click(within(matches).getByRole("button", { name: "Link to donor D10007" }))
        await waitFor(() =>
            expect(resolveSubmissionMatchMock).toHaveBeenCalledWith("sub-donor-held", { donor_id: "donor-7" }),
        )
        await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Submission linked to donor"))

        fireEvent.change(screen.getByLabelText("Search donors"), { target: { value: "Ri" } })
        const results = await screen.findByRole("list", { name: "Donor search results" })
        expect(listDonorsMock).toHaveBeenCalledWith({ donor_type: "egg", q: "Ri", per_page: 10 })
        expect(within(results).queryByText("D10007 · Casey Candidate")).not.toBeInTheDocument()
        fireEvent.click(within(results).getByRole("button", { name: "Link to donor D10008" }))
        await waitFor(() =>
            expect(resolveSubmissionMatchMock).toHaveBeenCalledWith("sub-donor-held", { donor_id: "donor-8" }),
        )
    })

    it("searches only the application's donor type and renders loading, error, and empty link states", async () => {
        const held = makeSubmission({ id: "sub-sperm", lead_kind: "sperm_donor", match_status: "ambiguous_review" })
        listSubmissionDonorCandidatesMock.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([])
        resolveSubmissionMatchMock.mockRejectedValue(new Error("Donor type does not match this application"))

        renderPanel({ ambiguousSubmissions: [held], canEditSubject: () => true })
        fireEvent.click(screen.getByRole("button", { name: "Link to Donor" }))
        expect(screen.getByText("Loading matching donors…")).toBeInTheDocument()

        expect(await screen.findByText("Unable to load matching donors.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("No matching donors.")).toBeInTheDocument()

        fireEvent.change(screen.getByLabelText("Search donors"), { target: { value: "R" } })
        expect(listDonorsMock).not.toHaveBeenCalled()
        fireEvent.change(screen.getByLabelText("Search donors"), { target: { value: "Rowan" } })
        expect(await screen.findByText("No donors found.")).toBeInTheDocument()
        expect(listDonorsMock).toHaveBeenCalledWith({ donor_type: "sperm", q: "Rowan", per_page: 10 })

        listDonorsMock.mockResolvedValue({
            items: [{ ...donorRecord("donor-9", "D10009", "Rowan Other"), donor_type: "sperm" }],
            total: 1,
            page: 1,
            per_page: 10,
            pages: 1,
        })
        fireEvent.change(screen.getByLabelText("Search donors"), { target: { value: "Rowan O" } })
        fireEvent.click(await screen.findByRole("button", { name: "Link to donor D10009" }))
        await waitFor(() =>
            expect(toastMock.error).toHaveBeenCalledWith("Donor type does not match this application"),
        )
    })

    it("approves a linked donor application and rejects a held one after confirmation", async () => {
        const linked = makeSubmission({
            id: "sub-linked",
            lead_kind: "egg_donor",
            donor_id: "donor-1",
            donor_number: "D10001",
            match_status: "linked",
            match_reason: "manually_linked",
        })
        const held = makeSubmission({
            id: "sub-held",
            lead_kind: "egg_donor",
            intake_lead_id: "lead-1",
            match_status: "lead_created",
            match_reason: "donor_photo_requires_review",
        })
        approveSubmissionMock.mockResolvedValue({ ...linked, status: "approved" })
        rejectSubmissionMock.mockResolvedValue({ ...held, status: "rejected" })

        renderPanel({ visibleSubmissionHistory: [linked, held], canEditSubject: () => true })

        expect(screen.getByText("Linked by reviewer")).toBeInTheDocument()
        expect(screen.getByText("Profile photo needs review")).toBeInTheDocument()
        expect(screen.getAllByRole("button", { name: "Link to Donor" })).toHaveLength(1)

        fireEvent.click(screen.getByRole("button", { name: "Approve" }))
        const approveDialog = await screen.findByRole("alertdialog", { name: "Approve this application?" })
        expect(approveSubmissionMock).not.toHaveBeenCalled()
        fireEvent.click(within(approveDialog).getByRole("button", { name: "Approve" }))
        await waitFor(() => expect(approveSubmissionMock).toHaveBeenCalledWith("sub-linked", undefined))
        await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Application approved"))

        fireEvent.click(screen.getAllByRole("button", { name: "Reject" })[1]!)
        const rejectDialog = await screen.findByRole("alertdialog", { name: "Reject this application?" })
        fireEvent.click(within(rejectDialog).getByRole("button", { name: "Reject" }))
        await waitFor(() => expect(rejectSubmissionMock).toHaveBeenCalledWith("sub-held", undefined))
    })

    it("keeps the approve dialog open with an inline error when approval fails", async () => {
        const linked = makeSubmission({
            id: "sub-linked",
            lead_kind: "egg_donor",
            donor_id: "donor-1",
            match_status: "linked",
        })
        approveSubmissionMock.mockRejectedValue(new Error("Missing permission: edit_donors"))

        renderPanel({ visibleSubmissionHistory: [linked], canEditSubject: () => true })
        fireEvent.click(screen.getByRole("button", { name: "Approve" }))
        const dialog = await screen.findByRole("alertdialog", { name: "Approve this application?" })
        fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }))
        expect(await within(dialog).findByRole("alert")).toBeInTheDocument()
        expect(toastMock.success).not.toHaveBeenCalled()
    })

    it("queues a rescan for a file whose scan failed and reports failures", async () => {
        const submission = makeSubmission({
            id: "sub-scan",
            lead_kind: "egg_donor",
            donor_id: "donor-1",
            match_status: "linked",
            status: "approved",
            files: [scanFile("file-error", "photo.jpg", "error"), scanFile("file-clean", "id.jpg", "clean")],
        })
        getSubmissionFileDownloadUrlMock.mockResolvedValue({ download_url: "https://files.example.test/id.jpg", filename: "id.jpg" })
        rescanSubmissionFileMock
            .mockResolvedValueOnce({ ...scanFile("file-error", "photo.jpg", "error"), scan_status: "pending" })
            .mockRejectedValueOnce(new Error("Only files whose scan failed can be rescanned"))

        renderPanel({ visibleSubmissionHistory: [submission], canEditSubject: () => true })

        expect(screen.queryByRole("button", { name: "Rescan id.jpg" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Rescan photo.jpg" }))
        await waitFor(() => expect(rescanSubmissionFileMock).toHaveBeenCalledWith("sub-scan", "file-error"))
        await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Rescan queued"))

        fireEvent.click(screen.getByRole("button", { name: "Rescan photo.jpg" }))
        await waitFor(() =>
            expect(toastMock.error).toHaveBeenCalledWith("Only files whose scan failed can be rescanned"),
        )
    })

    it("hides donor review and rescan controls without subject edit access or review access", () => {
        const held = makeSubmission({ id: "sub-held", lead_kind: "egg_donor", match_status: "ambiguous_review" })
        const scanFailed = makeSubmission({
            id: "sub-scan",
            lead_kind: "egg_donor",
            intake_lead_id: "lead-1",
            match_status: "lead_created",
            files: [scanFile("file-error", "photo.jpg", "error")],
        })

        const view = renderPanel({ ambiguousSubmissions: [held], visibleSubmissionHistory: [scanFailed] })
        expect(screen.getByText("photo.jpg")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Rescan photo.jpg" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Link to Donor" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument()

        view.unmount()
        renderPanel({ canReview: false, canEditSubject: () => true, visibleSubmissionHistory: [scanFailed] })
        expect(screen.queryByRole("button", { name: "Rescan photo.jpg" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Link to Donor" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument()
    })
})
