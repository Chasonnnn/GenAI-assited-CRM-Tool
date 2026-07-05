import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { AutomationFormSubmissionsPanel } from "@/components/forms/builder/AutomationFormSubmissionsPanel"
import type { FormSubmissionRead, MatchCandidateRead } from "@/lib/api/forms"

function makeSubmission(overrides: Partial<FormSubmissionRead>): FormSubmissionRead {
    return {
        id: "submission-1",
        form_id: "form-1",
        surrogate_id: null,
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
            reason: "Name and date of birth matched",
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

        fireEvent.click(screen.getByRole("button", { name: "Link Candidate" }))
        expect(onResolveSubmissionToSurrogate).toHaveBeenCalledWith("sub-ambiguous", "sur-candidate")
    })
})
