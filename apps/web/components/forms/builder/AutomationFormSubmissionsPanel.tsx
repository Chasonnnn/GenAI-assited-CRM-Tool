"use client"

import type { MatchCandidateRead, FormSubmissionRead } from "@/lib/api/forms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

type SubmissionHistoryFilter = "all" | "pending" | "processed"

type RetryMatchOptions = {
    unlinkSurrogate?: boolean
    unlinkIntakeLead?: boolean
    rerunAutoMatch?: boolean
    createIntakeLeadIfUnmatched?: boolean
}

type AutomationFormSubmissionsPanelProps = {
    formId: string | null
    pendingSubmissionHistory: FormSubmissionRead[]
    processedSubmissionHistory: FormSubmissionRead[]
    ambiguousSubmissions: FormSubmissionRead[]
    leadQueueSubmissions: FormSubmissionRead[]
    visibleSubmissionHistory: FormSubmissionRead[]
    submissionHistoryFilter: SubmissionHistoryFilter
    selectedQueueSubmissionId: string | null
    selectedMatchCandidates: MatchCandidateRead[]
    isSubmissionHistoryLoading: boolean
    isMatchCandidatesLoading: boolean
    retrySubmissionMatchPending: boolean
    resolveSubmissionMatchPending: boolean
    promoteIntakeLeadPending: boolean
    manualSurrogateId: string
    resolveReviewNotes: string
    readAnswerValue: (submission: FormSubmissionRead, keys: string[]) => string
    formatSubmissionDateTime: (isoString: string) => string
    submissionOutcomeLabel: (submission: FormSubmissionRead) => string
    submissionOutcomeBadgeClass: (submission: FormSubmissionRead) => string
    submissionReviewLabel: (submission: FormSubmissionRead) => string
    submissionReviewBadgeClass: (submission: FormSubmissionRead) => string
    onOpenApprovalQueue: () => void
    onSubmissionHistoryFilterChange: (value: SubmissionHistoryFilter) => void
    onSelectQueueSubmission: (submissionId: string | null) => void
    onManualSurrogateIdChange: (value: string) => void
    onResolveReviewNotesChange: (value: string) => void
    onLinkByManualSurrogateId: () => Promise<void> | void
    onResolveSubmissionToSurrogate: (submissionId: string, surrogateId: string) => Promise<void> | void
    onResolveSubmissionToLead: (submissionId: string) => Promise<void> | void
    onRetrySubmissionMatch: (
        submission: FormSubmissionRead,
        options: RetryMatchOptions,
        successMessage: string,
    ) => Promise<void> | void
    onPromoteLeadFromSubmission: (submission: FormSubmissionRead) => Promise<void> | void
}

export function AutomationFormSubmissionsPanel({
    formId,
    pendingSubmissionHistory,
    processedSubmissionHistory,
    ambiguousSubmissions,
    leadQueueSubmissions,
    visibleSubmissionHistory,
    submissionHistoryFilter,
    selectedQueueSubmissionId,
    selectedMatchCandidates,
    isSubmissionHistoryLoading,
    isMatchCandidatesLoading,
    retrySubmissionMatchPending,
    resolveSubmissionMatchPending,
    promoteIntakeLeadPending,
    manualSurrogateId,
    resolveReviewNotes,
    readAnswerValue,
    formatSubmissionDateTime,
    submissionOutcomeLabel,
    submissionOutcomeBadgeClass,
    submissionReviewLabel,
    submissionReviewBadgeClass,
    onOpenApprovalQueue,
    onSubmissionHistoryFilterChange,
    onSelectQueueSubmission,
    onManualSurrogateIdChange,
    onResolveReviewNotesChange,
    onLinkByManualSurrogateId,
    onResolveSubmissionToSurrogate,
    onResolveSubmissionToLead,
    onRetrySubmissionMatch,
    onPromoteLeadFromSubmission,
}: AutomationFormSubmissionsPanelProps) {
    return (
        <div className="mx-auto max-w-6xl space-y-6">
            <Card>
                <CardContent className="flex flex-col gap-3 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                        <p className="font-medium text-stone-900 dark:text-stone-100">
                            Workflow approvals for auto-match and lead creation
                        </p>
                        <p className="text-stone-600 dark:text-stone-400">
                            Approval-gated workflow actions appear in the shared approval queue.
                        </p>
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={onOpenApprovalQueue}>
                        Open Approval Queue
                    </Button>
                </CardContent>
            </Card>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Card>
                    <CardContent className="space-y-1 p-4">
                        <p className="text-xs uppercase tracking-wide text-stone-500">Pending Applications</p>
                        <p className="text-2xl font-semibold">{pendingSubmissionHistory.length}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="space-y-1 p-4">
                        <p className="text-xs uppercase tracking-wide text-stone-500">Processed Outcomes</p>
                        <p className="text-2xl font-semibold">{processedSubmissionHistory.length}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="space-y-1 p-4">
                        <p className="text-xs uppercase tracking-wide text-stone-500">Ambiguous Queue</p>
                        <p className="text-2xl font-semibold">{ambiguousSubmissions.length}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="space-y-1 p-4">
                        <p className="text-xs uppercase tracking-wide text-stone-500">Lead Queue</p>
                        <p className="text-2xl font-semibold">{leadQueueSubmissions.length}</p>
                    </CardContent>
                </Card>
            </div>

            {!formId ? (
                <Card>
                    <CardContent className="p-6 text-sm text-stone-600">
                        Create and publish the form before reviewing submissions.
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-6 xl:grid-cols-2">
                    <Card>
                        <CardContent className="space-y-4 p-5">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold">Ambiguous Match Queue</h3>
                                <Badge variant="outline">{ambiguousSubmissions.length}</Badge>
                            </div>
                            {ambiguousSubmissions.length === 0 ? (
                                <p className="text-sm text-stone-500">No ambiguous submissions.</p>
                            ) : (
                                <div className="space-y-3">
                                    {ambiguousSubmissions.map((submission) => {
                                        const fullName = readAnswerValue(submission, ["full_name", "name"])
                                        const dateOfBirth = readAnswerValue(submission, ["date_of_birth", "dob"])
                                        const phone = readAnswerValue(submission, [
                                            "phone",
                                            "phone_number",
                                            "mobile_phone",
                                        ])
                                        const email = readAnswerValue(submission, ["email", "email_address"])
                                        const isSelected = selectedQueueSubmissionId === submission.id

                                        return (
                                            <div
                                                key={submission.id}
                                                className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm"
                                            >
                                                <div className="grid gap-1 sm:grid-cols-2">
                                                    <div><span className="font-medium">Name:</span> {fullName}</div>
                                                    <div><span className="font-medium">DOB:</span> {dateOfBirth}</div>
                                                    <div><span className="font-medium">Phone:</span> {phone}</div>
                                                    <div><span className="font-medium">Email:</span> {email}</div>
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant={isSelected ? "default" : "outline"}
                                                        onClick={() =>
                                                            onSelectQueueSubmission(isSelected ? null : submission.id)
                                                        }
                                                    >
                                                        {isSelected ? "Hide Candidates" : "Review Candidates"}
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={resolveSubmissionMatchPending}
                                                        onClick={() => void onResolveSubmissionToLead(submission.id)}
                                                    >
                                                        Keep As Lead
                                                    </Button>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardContent className="space-y-4 p-5">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold">Lead Promotion Queue</h3>
                                <Badge variant="outline">{leadQueueSubmissions.length}</Badge>
                            </div>
                            {leadQueueSubmissions.length === 0 ? (
                                <p className="text-sm text-stone-500">No pending lead submissions.</p>
                            ) : (
                                <div className="space-y-3">
                                    {leadQueueSubmissions.map((submission) => {
                                        const fullName = readAnswerValue(submission, ["full_name", "name"])
                                        const dateOfBirth = readAnswerValue(submission, ["date_of_birth", "dob"])
                                        const phone = readAnswerValue(submission, [
                                            "phone",
                                            "phone_number",
                                            "mobile_phone",
                                        ])
                                        const email = readAnswerValue(submission, ["email", "email_address"])

                                        return (
                                            <div
                                                key={submission.id}
                                                className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm"
                                            >
                                                <div className="grid gap-1 sm:grid-cols-2">
                                                    <div><span className="font-medium">Name:</span> {fullName}</div>
                                                    <div><span className="font-medium">DOB:</span> {dateOfBirth}</div>
                                                    <div><span className="font-medium">Phone:</span> {phone}</div>
                                                    <div><span className="font-medium">Email:</span> {email}</div>
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={promoteIntakeLeadPending || !submission.intake_lead_id}
                                                        onClick={() => void onPromoteLeadFromSubmission(submission)}
                                                    >
                                                        Promote Lead
                                                    </Button>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}

            <Card>
                <CardContent className="space-y-4 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold">Submission History</h3>
                        <div className="flex items-center gap-2">
                            <Button
                                type="button"
                                size="sm"
                                variant={submissionHistoryFilter === "all" ? "default" : "outline"}
                                onClick={() => onSubmissionHistoryFilterChange("all")}
                            >
                                All
                            </Button>
                            <Button
                                type="button"
                                size="sm"
                                variant={submissionHistoryFilter === "pending" ? "default" : "outline"}
                                onClick={() => onSubmissionHistoryFilterChange("pending")}
                            >
                                Pending
                            </Button>
                            <Button
                                type="button"
                                size="sm"
                                variant={submissionHistoryFilter === "processed" ? "default" : "outline"}
                                onClick={() => onSubmissionHistoryFilterChange("processed")}
                            >
                                Processed
                            </Button>
                        </div>
                    </div>

                    {isSubmissionHistoryLoading ? (
                        <p className="text-sm text-stone-500">Loading submission history...</p>
                    ) : visibleSubmissionHistory.length === 0 ? (
                        <p className="text-sm text-stone-500">No submissions in this view.</p>
                    ) : (
                        <div className="space-y-3">
                            {visibleSubmissionHistory.map((submission) => {
                                const fullName = readAnswerValue(submission, ["full_name", "name"])
                                const email = readAnswerValue(submission, ["email", "email_address"])
                                const phone = readAnswerValue(submission, ["phone", "phone_number", "mobile_phone"])
                                const canReviewCandidates =
                                    submission.source_mode === "shared" &&
                                    submission.match_status === "ambiguous_review"
                                const canReprocess = submission.source_mode === "shared"

                                return (
                                    <div
                                        key={submission.id}
                                        className="space-y-3 rounded-lg border border-stone-200 p-3 text-sm"
                                    >
                                        <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant="outline">
                                                {submission.source_mode === "shared" ? "Shared" : "Dedicated"}
                                            </Badge>
                                            <Badge
                                                variant="outline"
                                                className={submissionOutcomeBadgeClass(submission)}
                                            >
                                                {submissionOutcomeLabel(submission)}
                                            </Badge>
                                            <Badge
                                                variant="outline"
                                                className={submissionReviewBadgeClass(submission)}
                                            >
                                                {submissionReviewLabel(submission)}
                                            </Badge>
                                        </div>
                                        <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
                                            <div><span className="font-medium">Name:</span> {fullName}</div>
                                            <div><span className="font-medium">Email:</span> {email}</div>
                                            <div><span className="font-medium">Phone:</span> {phone}</div>
                                            <div>
                                                <span className="font-medium">Submitted:</span>{" "}
                                                {formatSubmissionDateTime(submission.submitted_at)}
                                            </div>
                                            <div>
                                                <span className="font-medium">Surrogate:</span>{" "}
                                                {submission.surrogate_id ? submission.surrogate_id : "—"}
                                            </div>
                                            <div>
                                                <span className="font-medium">Lead:</span>{" "}
                                                {submission.intake_lead_id ? submission.intake_lead_id : "—"}
                                            </div>
                                        </div>
                                        <div className="flex flex-wrap justify-end gap-2">
                                            {canReviewCandidates && (
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => onSelectQueueSubmission(submission.id)}
                                                >
                                                    Review Candidates
                                                </Button>
                                            )}
                                            {canReprocess && (
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    disabled={retrySubmissionMatchPending}
                                                    onClick={() =>
                                                        void onRetrySubmissionMatch(
                                                            submission,
                                                            {
                                                                unlinkSurrogate: Boolean(submission.surrogate_id),
                                                                rerunAutoMatch: true,
                                                            },
                                                            "Auto-match re-run complete",
                                                        )
                                                    }
                                                >
                                                    Re-run Auto-Match
                                                </Button>
                                            )}
                                            {submission.surrogate_id && (
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    disabled={retrySubmissionMatchPending}
                                                    onClick={() =>
                                                        void onRetrySubmissionMatch(
                                                            submission,
                                                            {
                                                                unlinkSurrogate: true,
                                                                rerunAutoMatch: false,
                                                            },
                                                            "Submission unlinked. Select the correct surrogate.",
                                                        )
                                                    }
                                                >
                                                    Unlink
                                                </Button>
                                            )}
                                            {submission.intake_lead_id && (
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="outline"
                                                    disabled={retrySubmissionMatchPending}
                                                    onClick={() =>
                                                        void onRetrySubmissionMatch(
                                                            submission,
                                                            {
                                                                unlinkSurrogate: Boolean(submission.surrogate_id),
                                                                unlinkIntakeLead: true,
                                                                rerunAutoMatch: true,
                                                                createIntakeLeadIfUnmatched: true,
                                                            },
                                                            "Lead link reset and submission reprocessed",
                                                        )
                                                    }
                                                >
                                                    Undo Lead + Reprocess
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>

            {selectedQueueSubmissionId && (
                <Card>
                    <CardContent className="space-y-4 p-5">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold">Match Candidates</h3>
                            <Badge variant="outline">{selectedMatchCandidates.length}</Badge>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="queue-review-notes-submissions">Reviewer notes</Label>
                            <Textarea
                                id="queue-review-notes-submissions"
                                rows={2}
                                value={resolveReviewNotes}
                                onChange={(event) => onResolveReviewNotesChange(event.target.value)}
                                placeholder="Why this match was resolved..."
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="manual-surrogate-id-submissions">Manual surrogate ID link</Label>
                            <div className="flex flex-wrap gap-2">
                                <Input
                                    id="manual-surrogate-id-submissions"
                                    value={manualSurrogateId}
                                    onChange={(event) => onManualSurrogateIdChange(event.target.value)}
                                    placeholder="Paste surrogate UUID"
                                />
                                <Button
                                    type="button"
                                    variant="outline"
                                    disabled={resolveSubmissionMatchPending}
                                    onClick={() => void onLinkByManualSurrogateId()}
                                >
                                    Link Surrogate ID
                                </Button>
                            </div>
                        </div>

                        {isMatchCandidatesLoading ? (
                            <p className="text-sm text-stone-500">Loading candidates...</p>
                        ) : selectedMatchCandidates.length === 0 ? (
                            <p className="text-sm text-stone-500">No candidates found.</p>
                        ) : (
                            <div className="space-y-2">
                                {selectedMatchCandidates.map((candidate) => (
                                    <div
                                        key={candidate.id}
                                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-200 p-3 text-sm"
                                    >
                                        <div className="space-y-1">
                                            <p className="font-mono text-xs text-stone-600">
                                                surrogate_id: {candidate.surrogate_id}
                                            </p>
                                            <p className="text-xs text-stone-500">{candidate.reason}</p>
                                        </div>
                                        <Button
                                            type="button"
                                            size="sm"
                                            onClick={() =>
                                                void onResolveSubmissionToSurrogate(
                                                    selectedQueueSubmissionId,
                                                    candidate.surrogate_id,
                                                )
                                            }
                                            disabled={resolveSubmissionMatchPending}
                                        >
                                            Link Candidate
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
