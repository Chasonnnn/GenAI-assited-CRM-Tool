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

type SubmissionIdentity = {
    fullName: string
    dateOfBirth: string
    phone: string
    email: string
}

type SubmissionIdentityReader = AutomationFormSubmissionsPanelProps["readAnswerValue"]

function readSubmissionIdentity(
    submission: FormSubmissionRead,
    readAnswerValue: SubmissionIdentityReader,
): SubmissionIdentity {
    return {
        fullName: readAnswerValue(submission, ["full_name", "name"]),
        dateOfBirth: readAnswerValue(submission, ["date_of_birth", "dob"]),
        phone: readAnswerValue(submission, ["phone", "phone_number", "mobile_phone"]),
        email: readAnswerValue(submission, ["email", "email_address"]),
    }
}

function WorkflowApprovalCard({
    onOpenApprovalQueue,
}: {
    onOpenApprovalQueue: () => void
}) {
    return (
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
    )
}

function SubmissionMetricCard({
    label,
    value,
}: {
    label: string
    value: number
}) {
    return (
        <Card>
            <CardContent className="space-y-1 p-4">
                <p className="text-xs uppercase tracking-wide text-stone-500">{label}</p>
                <p className="text-2xl font-semibold">{value}</p>
            </CardContent>
        </Card>
    )
}

function SubmissionMetricsGrid({
    pendingSubmissionHistory,
    processedSubmissionHistory,
    ambiguousSubmissions,
    leadQueueSubmissions,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "pendingSubmissionHistory"
    | "processedSubmissionHistory"
    | "ambiguousSubmissions"
    | "leadQueueSubmissions"
>) {
    return (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SubmissionMetricCard label="Pending Applications" value={pendingSubmissionHistory.length} />
            <SubmissionMetricCard label="Processed Outcomes" value={processedSubmissionHistory.length} />
            <SubmissionMetricCard label="Ambiguous Queue" value={ambiguousSubmissions.length} />
            <SubmissionMetricCard label="Lead Queue" value={leadQueueSubmissions.length} />
        </div>
    )
}

function SubmissionIdentityGrid({
    identity,
}: {
    identity: SubmissionIdentity
}) {
    return (
        <div className="grid gap-1 sm:grid-cols-2">
            <div><span className="font-medium">Name:</span> {identity.fullName}</div>
            <div><span className="font-medium">DOB:</span> {identity.dateOfBirth}</div>
            <div><span className="font-medium">Phone:</span> {identity.phone}</div>
            <div><span className="font-medium">Email:</span> {identity.email}</div>
        </div>
    )
}

function AmbiguousSubmissionCard({
    submission,
    isSelected,
    readAnswerValue,
    resolveSubmissionMatchPending,
    onSelectQueueSubmission,
    onResolveSubmissionToLead,
}: {
    submission: FormSubmissionRead
    isSelected: boolean
    readAnswerValue: SubmissionIdentityReader
    resolveSubmissionMatchPending: boolean
    onSelectQueueSubmission: (submissionId: string | null) => void
    onResolveSubmissionToLead: (submissionId: string) => Promise<void> | void
}) {
    const identity = readSubmissionIdentity(submission, readAnswerValue)

    return (
        <div className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm">
            <SubmissionIdentityGrid identity={identity} />
            <div className="flex flex-wrap gap-2">
                <Button
                    type="button"
                    size="sm"
                    variant={isSelected ? "default" : "outline"}
                    onClick={() => onSelectQueueSubmission(isSelected ? null : submission.id)}
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
}

function AmbiguousMatchQueueCard({
    ambiguousSubmissions,
    selectedQueueSubmissionId,
    readAnswerValue,
    resolveSubmissionMatchPending,
    onSelectQueueSubmission,
    onResolveSubmissionToLead,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "ambiguousSubmissions"
    | "selectedQueueSubmissionId"
    | "readAnswerValue"
    | "resolveSubmissionMatchPending"
    | "onSelectQueueSubmission"
    | "onResolveSubmissionToLead"
>) {
    return (
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
                        {ambiguousSubmissions.map((submission) => (
                            <AmbiguousSubmissionCard
                                key={submission.id}
                                submission={submission}
                                isSelected={selectedQueueSubmissionId === submission.id}
                                readAnswerValue={readAnswerValue}
                                resolveSubmissionMatchPending={resolveSubmissionMatchPending}
                                onSelectQueueSubmission={onSelectQueueSubmission}
                                onResolveSubmissionToLead={onResolveSubmissionToLead}
                            />
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function LeadPromotionSubmissionCard({
    submission,
    readAnswerValue,
    promoteIntakeLeadPending,
    onPromoteLeadFromSubmission,
}: {
    submission: FormSubmissionRead
    readAnswerValue: SubmissionIdentityReader
    promoteIntakeLeadPending: boolean
    onPromoteLeadFromSubmission: (submission: FormSubmissionRead) => Promise<void> | void
}) {
    const identity = readSubmissionIdentity(submission, readAnswerValue)

    return (
        <div className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm">
            <SubmissionIdentityGrid identity={identity} />
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
}

function LeadPromotionQueueCard({
    leadQueueSubmissions,
    readAnswerValue,
    promoteIntakeLeadPending,
    onPromoteLeadFromSubmission,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "leadQueueSubmissions"
    | "readAnswerValue"
    | "promoteIntakeLeadPending"
    | "onPromoteLeadFromSubmission"
>) {
    return (
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
                        {leadQueueSubmissions.map((submission) => (
                            <LeadPromotionSubmissionCard
                                key={submission.id}
                                submission={submission}
                                readAnswerValue={readAnswerValue}
                                promoteIntakeLeadPending={promoteIntakeLeadPending}
                                onPromoteLeadFromSubmission={onPromoteLeadFromSubmission}
                            />
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function SubmissionReviewQueues({
    formId,
    ambiguousSubmissions,
    leadQueueSubmissions,
    selectedQueueSubmissionId,
    readAnswerValue,
    resolveSubmissionMatchPending,
    promoteIntakeLeadPending,
    onSelectQueueSubmission,
    onResolveSubmissionToLead,
    onPromoteLeadFromSubmission,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "formId"
    | "ambiguousSubmissions"
    | "leadQueueSubmissions"
    | "selectedQueueSubmissionId"
    | "readAnswerValue"
    | "resolveSubmissionMatchPending"
    | "promoteIntakeLeadPending"
    | "onSelectQueueSubmission"
    | "onResolveSubmissionToLead"
    | "onPromoteLeadFromSubmission"
>) {
    if (!formId) {
        return (
            <Card>
                <CardContent className="p-6 text-sm text-stone-600">
                    Create and publish the form before reviewing submissions.
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="grid gap-6 xl:grid-cols-2">
            <AmbiguousMatchQueueCard
                ambiguousSubmissions={ambiguousSubmissions}
                selectedQueueSubmissionId={selectedQueueSubmissionId}
                readAnswerValue={readAnswerValue}
                resolveSubmissionMatchPending={resolveSubmissionMatchPending}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onResolveSubmissionToLead={onResolveSubmissionToLead}
            />
            <LeadPromotionQueueCard
                leadQueueSubmissions={leadQueueSubmissions}
                readAnswerValue={readAnswerValue}
                promoteIntakeLeadPending={promoteIntakeLeadPending}
                onPromoteLeadFromSubmission={onPromoteLeadFromSubmission}
            />
        </div>
    )
}

function SubmissionHistoryFilters({
    submissionHistoryFilter,
    onSubmissionHistoryFilterChange,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    "submissionHistoryFilter" | "onSubmissionHistoryFilterChange"
>) {
    return (
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
    )
}

function SubmissionHistoryIdentityGrid({
    submission,
    readAnswerValue,
    formatSubmissionDateTime,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    "readAnswerValue" | "formatSubmissionDateTime"
> & {
    submission: FormSubmissionRead
}) {
    const fullName = readAnswerValue(submission, ["full_name", "name"])
    const email = readAnswerValue(submission, ["email", "email_address"])
    const phone = readAnswerValue(submission, ["phone", "phone_number", "mobile_phone"])

    return (
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
    )
}

function SubmissionHistoryBadges({
    submission,
    submissionOutcomeLabel,
    submissionOutcomeBadgeClass,
    submissionReviewLabel,
    submissionReviewBadgeClass,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "submissionOutcomeLabel"
    | "submissionOutcomeBadgeClass"
    | "submissionReviewLabel"
    | "submissionReviewBadgeClass"
> & {
    submission: FormSubmissionRead
}) {
    return (
        <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Shared</Badge>
            <Badge variant="outline" className={submissionOutcomeBadgeClass(submission)}>
                {submissionOutcomeLabel(submission)}
            </Badge>
            <Badge variant="outline" className={submissionReviewBadgeClass(submission)}>
                {submissionReviewLabel(submission)}
            </Badge>
        </div>
    )
}

function SubmissionHistoryActions({
    submission,
    retrySubmissionMatchPending,
    onSelectQueueSubmission,
    onRetrySubmissionMatch,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    "retrySubmissionMatchPending" | "onSelectQueueSubmission" | "onRetrySubmissionMatch"
> & {
    submission: FormSubmissionRead
}) {
    const canReviewCandidates =
        submission.source_mode === "shared" &&
        submission.match_status === "ambiguous_review"
    const canReprocess = submission.source_mode === "shared"

    return (
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
    )
}

function SubmissionHistoryEntry({
    submission,
    readAnswerValue,
    formatSubmissionDateTime,
    submissionOutcomeLabel,
    submissionOutcomeBadgeClass,
    submissionReviewLabel,
    submissionReviewBadgeClass,
    retrySubmissionMatchPending,
    onSelectQueueSubmission,
    onRetrySubmissionMatch,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "readAnswerValue"
    | "formatSubmissionDateTime"
    | "submissionOutcomeLabel"
    | "submissionOutcomeBadgeClass"
    | "submissionReviewLabel"
    | "submissionReviewBadgeClass"
    | "retrySubmissionMatchPending"
    | "onSelectQueueSubmission"
    | "onRetrySubmissionMatch"
> & {
    submission: FormSubmissionRead
}) {
    return (
        <div className="space-y-3 rounded-lg border border-stone-200 p-3 text-sm">
            <SubmissionHistoryBadges
                submission={submission}
                submissionOutcomeLabel={submissionOutcomeLabel}
                submissionOutcomeBadgeClass={submissionOutcomeBadgeClass}
                submissionReviewLabel={submissionReviewLabel}
                submissionReviewBadgeClass={submissionReviewBadgeClass}
            />
            <SubmissionHistoryIdentityGrid
                submission={submission}
                readAnswerValue={readAnswerValue}
                formatSubmissionDateTime={formatSubmissionDateTime}
            />
            <SubmissionHistoryActions
                submission={submission}
                retrySubmissionMatchPending={retrySubmissionMatchPending}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onRetrySubmissionMatch={onRetrySubmissionMatch}
            />
        </div>
    )
}

function SubmissionHistoryCard({
    visibleSubmissionHistory,
    submissionHistoryFilter,
    isSubmissionHistoryLoading,
    readAnswerValue,
    formatSubmissionDateTime,
    submissionOutcomeLabel,
    submissionOutcomeBadgeClass,
    submissionReviewLabel,
    submissionReviewBadgeClass,
    retrySubmissionMatchPending,
    onSubmissionHistoryFilterChange,
    onSelectQueueSubmission,
    onRetrySubmissionMatch,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "visibleSubmissionHistory"
    | "submissionHistoryFilter"
    | "isSubmissionHistoryLoading"
    | "readAnswerValue"
    | "formatSubmissionDateTime"
    | "submissionOutcomeLabel"
    | "submissionOutcomeBadgeClass"
    | "submissionReviewLabel"
    | "submissionReviewBadgeClass"
    | "retrySubmissionMatchPending"
    | "onSubmissionHistoryFilterChange"
    | "onSelectQueueSubmission"
    | "onRetrySubmissionMatch"
>) {
    return (
        <Card>
            <CardContent className="space-y-4 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold">Submission History</h3>
                    <SubmissionHistoryFilters
                        submissionHistoryFilter={submissionHistoryFilter}
                        onSubmissionHistoryFilterChange={onSubmissionHistoryFilterChange}
                    />
                </div>

                {isSubmissionHistoryLoading ? (
                    <p className="text-sm text-stone-500">Loading submission history…</p>
                ) : visibleSubmissionHistory.length === 0 ? (
                    <p className="text-sm text-stone-500">No submissions in this view.</p>
                ) : (
                    <div className="space-y-3">
                        {visibleSubmissionHistory.map((submission) => (
                            <SubmissionHistoryEntry
                                key={submission.id}
                                submission={submission}
                                readAnswerValue={readAnswerValue}
                                formatSubmissionDateTime={formatSubmissionDateTime}
                                submissionOutcomeLabel={submissionOutcomeLabel}
                                submissionOutcomeBadgeClass={submissionOutcomeBadgeClass}
                                submissionReviewLabel={submissionReviewLabel}
                                submissionReviewBadgeClass={submissionReviewBadgeClass}
                                retrySubmissionMatchPending={retrySubmissionMatchPending}
                                onSelectQueueSubmission={onSelectQueueSubmission}
                                onRetrySubmissionMatch={onRetrySubmissionMatch}
                            />
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function SubmissionCandidateReviewCard({
    selectedQueueSubmissionId,
    selectedMatchCandidates,
    isMatchCandidatesLoading,
    resolveSubmissionMatchPending,
    manualSurrogateId,
    resolveReviewNotes,
    onManualSurrogateIdChange,
    onResolveReviewNotesChange,
    onLinkByManualSurrogateId,
    onResolveSubmissionToSurrogate,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "selectedQueueSubmissionId"
    | "selectedMatchCandidates"
    | "isMatchCandidatesLoading"
    | "resolveSubmissionMatchPending"
    | "manualSurrogateId"
    | "resolveReviewNotes"
    | "onManualSurrogateIdChange"
    | "onResolveReviewNotesChange"
    | "onLinkByManualSurrogateId"
    | "onResolveSubmissionToSurrogate"
>) {
    if (!selectedQueueSubmissionId) {
        return null
    }

    return (
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
                        placeholder="Why this match was resolved…"
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
                    <p className="text-sm text-stone-500">Loading candidates…</p>
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
    )
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
            <WorkflowApprovalCard onOpenApprovalQueue={onOpenApprovalQueue} />
            <SubmissionMetricsGrid
                pendingSubmissionHistory={pendingSubmissionHistory}
                processedSubmissionHistory={processedSubmissionHistory}
                ambiguousSubmissions={ambiguousSubmissions}
                leadQueueSubmissions={leadQueueSubmissions}
            />
            <SubmissionReviewQueues
                formId={formId}
                ambiguousSubmissions={ambiguousSubmissions}
                leadQueueSubmissions={leadQueueSubmissions}
                selectedQueueSubmissionId={selectedQueueSubmissionId}
                readAnswerValue={readAnswerValue}
                resolveSubmissionMatchPending={resolveSubmissionMatchPending}
                promoteIntakeLeadPending={promoteIntakeLeadPending}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onResolveSubmissionToLead={onResolveSubmissionToLead}
                onPromoteLeadFromSubmission={onPromoteLeadFromSubmission}
            />
            <SubmissionHistoryCard
                visibleSubmissionHistory={visibleSubmissionHistory}
                submissionHistoryFilter={submissionHistoryFilter}
                isSubmissionHistoryLoading={isSubmissionHistoryLoading}
                readAnswerValue={readAnswerValue}
                formatSubmissionDateTime={formatSubmissionDateTime}
                submissionOutcomeLabel={submissionOutcomeLabel}
                submissionOutcomeBadgeClass={submissionOutcomeBadgeClass}
                submissionReviewLabel={submissionReviewLabel}
                submissionReviewBadgeClass={submissionReviewBadgeClass}
                retrySubmissionMatchPending={retrySubmissionMatchPending}
                onSubmissionHistoryFilterChange={onSubmissionHistoryFilterChange}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onRetrySubmissionMatch={onRetrySubmissionMatch}
            />
            <SubmissionCandidateReviewCard
                selectedQueueSubmissionId={selectedQueueSubmissionId}
                selectedMatchCandidates={selectedMatchCandidates}
                isMatchCandidatesLoading={isMatchCandidatesLoading}
                resolveSubmissionMatchPending={resolveSubmissionMatchPending}
                manualSurrogateId={manualSurrogateId}
                resolveReviewNotes={resolveReviewNotes}
                onManualSurrogateIdChange={onManualSurrogateIdChange}
                onResolveReviewNotesChange={onResolveReviewNotesChange}
                onLinkByManualSurrogateId={onLinkByManualSurrogateId}
                onResolveSubmissionToSurrogate={onResolveSubmissionToSurrogate}
            />
        </div>
    )
}
