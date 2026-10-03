"use client"

import Image from "next/image"
import Link from "next/link"
import type { Route } from "next"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import {
    getSubmissionFileDownloadUrl,
    type FormLeadKind,
    type FormSubmissionRead,
    type MatchCandidateRead,
    type ResolveSubmissionMatchResponse,
} from "@/lib/api/forms"
import { FORM_LEAD_KIND_LABELS, isDonorFormLeadKind } from "@/lib/forms/form-lead-kind"
import { getRoutingReviewStepLabel } from "@/lib/forms/form-routing"
import { matchReasonLabel } from "@/lib/forms/submission-presentation"
import { useDonors } from "@/lib/hooks/use-donors"
import {
    useApproveFormSubmission,
    useCreateSubmissionRoutingLead,
    useDismissSubmissionRoutingReview,
    useRejectFormSubmission,
    useRescanSubmissionFile,
    useResolveSubmissionMatch,
    useRunSubmissionRoutingMatch,
    useSubmissionDonorCandidates,
} from "@/lib/hooks/use-forms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"

type SubmissionHistoryFilter = "all" | "pending" | "processed"

type RetryMatchOptions = {
    unlinkSurrogate?: boolean
    unlinkIntakeLead?: boolean
    rerunAutoMatch?: boolean
    createIntakeLeadIfUnmatched?: boolean
}

type RoutingReviewAction = "review" | "create_lead"

type RoutingReviewQueueStatus = "loading" | "error" | "ready"

type AutomationFormSubmissionsPanelProps = {
    canPromoteLead?: ((submission: FormSubmissionRead) => boolean) | undefined
    canEditSubject?: ((submission: FormSubmissionRead) => boolean) | undefined
    /** Subject and record-creation access for routing review actions; omitted means allowed. */
    canReviewRouting?: ((submission: FormSubmissionRead, action: RoutingReviewAction) => boolean) | undefined
    canReview?: boolean
    formId: string | null
    pendingSubmissionHistory: FormSubmissionRead[]
    processedSubmissionHistory: FormSubmissionRead[]
    routingReviewSubmissions: FormSubmissionRead[]
    /** Load state of the routing review queue; its count and empty state show only when ready. */
    routingReviewQueueStatus: RoutingReviewQueueStatus
    isRoutingReviewRetrying: boolean
    onRetryRoutingReview: () => void
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
    state: string
    education: string
}

type SubmissionIdentityReader = AutomationFormSubmissionsPanelProps["readAnswerValue"]

function donorPhotoAlt(leadKind: FormLeadKind): string {
    const label = FORM_LEAD_KIND_LABELS[leadKind].replace("Donor", "donor")
    return `${label} profile photo`
}

function DonorProfilePhotoPreview({ submission }: { submission: FormSubmissionRead }) {
    const cleanImages = submission.files.filter(
        (file) =>
            file.content_type.startsWith("image/") &&
            file.scan_status === "clean" &&
            !file.quarantined,
    )
    const photo =
        cleanImages.find((file) => file.field_key === "profile_photo") ?? cleanImages[0]
    const photoQuery = useQuery({
        queryKey: ["forms", "submission-photo", submission.id, photo?.id ?? "missing"],
        queryFn: () => getSubmissionFileDownloadUrl(submission.id, photo!.id),
        enabled: isDonorFormLeadKind(submission.lead_kind) && Boolean(photo),
        staleTime: 4 * 60 * 1000,
    })

    if (!isDonorFormLeadKind(submission.lead_kind) || !photo) return null
    if (!photoQuery.data?.download_url) {
        return <div className="size-16 rounded-md border bg-muted/30" aria-label="Profile photo unavailable" />
    }
    return (
        <Image
            src={photoQuery.data.download_url}
            alt={donorPhotoAlt(submission.lead_kind)}
            width={64}
            height={64}
            unoptimized
            referrerPolicy="no-referrer"
            className="size-16 rounded-md border object-cover"
        />
    )
}

function readSubmissionIdentity(
    submission: FormSubmissionRead,
    readAnswerValue: SubmissionIdentityReader,
): SubmissionIdentity {
    return {
        fullName: readAnswerValue(submission, ["full_name", "name"]),
        dateOfBirth: readAnswerValue(submission, ["date_of_birth", "dob"]),
        phone: readAnswerValue(submission, ["phone", "phone_number", "mobile_phone"]),
        email: readAnswerValue(submission, ["email", "email_address"]),
        state: readAnswerValue(submission, ["state", "residence_state"]),
        education: readAnswerValue(submission, ["education", "education_level"]),
    }
}

type SubjectEditCheck = (submission: FormSubmissionRead) => boolean

function errorMessage(error: unknown, fallback: string) {
    return error instanceof Error && error.message ? error.message : fallback
}

function isPendingDonorReview(submission: FormSubmissionRead) {
    return isDonorFormLeadKind(submission.lead_kind) && submission.status === "pending_review"
}

function MatchReason({ submission }: { submission: FormSubmissionRead }) {
    if (!submission.match_reason) return null
    return (
        <div>
            <span className="font-medium">Reason:</span> {matchReasonLabel(submission.match_reason)}
        </div>
    )
}

function DonorOption({
    donorNumber,
    fullName,
    reason,
    disabled,
    onLink,
}: {
    donorNumber: string
    fullName: string
    reason?: string
    disabled: boolean
    onLink: () => void
}) {
    return (
        <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-stone-200 p-2">
            <div className="min-w-0">
                <p className="font-medium">{donorNumber} · {fullName}</p>
                {reason ? <p className="text-xs text-stone-500">{reason}</p> : null}
            </div>
            <Button
                type="button"
                size="sm"
                disabled={disabled}
                aria-label={`Link to donor ${donorNumber}`}
                onClick={onLink}
            >
                Link
            </Button>
        </li>
    )
}

function DonorLinkReview({ submission }: { submission: FormSubmissionRead }) {
    const [search, setSearch] = useState("")
    const query = search.trim()
    const candidates = useSubmissionDonorCandidates(submission.id)
    const searchResults = useDonors(
        { donor_type: submission.lead_kind === "sperm_donor" ? "sperm" : "egg", q: query, per_page: 10 },
        { enabled: query.length >= 2 },
    )
    const resolve = useResolveSubmissionMatch()
    const link = async (donorId: string) => {
        try {
            await resolve.mutateAsync({ submissionId: submission.id, payload: { donor_id: donorId } })
            toast.success("Submission linked to donor")
        } catch (error) {
            toast.error(errorMessage(error, "Unable to link submission"))
        }
    }
    const candidateItems = candidates.data ?? []
    const candidateIds = new Set(candidateItems.map((candidate) => candidate.donor_id))
    const searchItems = (searchResults.data?.items ?? []).filter((donor) => !candidateIds.has(donor.id))
    const searchId = `donor-search-${submission.id}`

    return (
        <div className="space-y-3 rounded-md border border-stone-200 p-3">
            <h4 className="text-sm font-semibold">Link to Donor</h4>
            {candidates.isLoading ? (
                <p className="text-stone-500">Loading matching donors…</p>
            ) : candidates.isError ? (
                <div role="alert" className="flex flex-wrap items-center gap-2">
                    <p>Unable to load matching donors.</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => void candidates.refetch()}>
                        Retry
                    </Button>
                </div>
            ) : candidateItems.length === 0 ? (
                <p className="text-stone-500">No matching donors.</p>
            ) : (
                <ul className="space-y-2" aria-label="Matching donors">
                    {candidateItems.map((candidate) => (
                        <DonorOption
                            key={candidate.donor_id}
                            donorNumber={candidate.donor_number}
                            fullName={candidate.full_name}
                            reason={matchReasonLabel(candidate.reason)}
                            disabled={resolve.isPending}
                            onLink={() => void link(candidate.donor_id)}
                        />
                    ))}
                </ul>
            )}
            <div className="space-y-2">
                <Label htmlFor={searchId}>Search donors</Label>
                <Input
                    id={searchId}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Name, number, email or phone"
                />
            </div>
            {query.length < 2 ? null : searchResults.isLoading ? (
                <p className="text-stone-500">Searching donors…</p>
            ) : searchResults.isError ? (
                <div role="alert" className="flex flex-wrap items-center gap-2">
                    <p>Unable to search donors.</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => void searchResults.refetch()}>
                        Retry
                    </Button>
                </div>
            ) : searchItems.length === 0 ? (
                <p className="text-stone-500">No donors found.</p>
            ) : (
                <ul className="space-y-2" aria-label="Donor search results">
                    {searchItems.map((donor) => (
                        <DonorOption
                            key={donor.id}
                            donorNumber={donor.donor_number}
                            fullName={donor.full_name}
                            disabled={resolve.isPending}
                            onLink={() => void link(donor.id)}
                        />
                    ))}
                </ul>
            )}
        </div>
    )
}

/** Link, approve and reject controls for a pending donor application; the caller checks access. */
function DonorReviewControls({
    submission,
    align = "start",
}: {
    submission: FormSubmissionRead
    align?: "start" | "end"
}) {
    const [linkOpen, setLinkOpen] = useState(false)
    const approve = useApproveFormSubmission()
    const reject = useRejectFormSubmission()
    const canLink = !submission.donor_id

    return (
        <div className="space-y-3">
            <div className={`flex flex-wrap gap-2 ${align === "end" ? "justify-end" : ""}`}>
                {canLink ? (
                    <Button
                        type="button"
                        size="sm"
                        variant={linkOpen ? "default" : "outline"}
                        aria-expanded={linkOpen}
                        onClick={() => setLinkOpen((open) => !open)}
                    >
                        Link to Donor
                    </Button>
                ) : (
                    <ConfirmDialog
                        title="Approve this application?"
                        confirmLabel="Approve"
                        confirmVariant="default"
                        errorFallback="Unable to approve application"
                        onConfirm={() =>
                            approve.mutateAsync({ submissionId: submission.id }).then(() => {
                                toast.success("Application approved")
                            })
                        }
                        trigger={<Button type="button" size="sm" variant="outline">Approve</Button>}
                    />
                )}
                <ConfirmDialog
                    title="Reject this application?"
                    confirmLabel="Reject"
                    errorFallback="Unable to reject application"
                    onConfirm={() =>
                        reject.mutateAsync({ submissionId: submission.id }).then(() => {
                            toast.success("Application rejected")
                        })
                    }
                    trigger={<Button type="button" size="sm" variant="outline">Reject</Button>}
                />
            </div>
            {canLink && linkOpen ? <DonorLinkReview submission={submission} /> : null}
        </div>
    )
}

function FailedScanFiles({ submission, canRescan }: { submission: FormSubmissionRead; canRescan: boolean }) {
    const rescan = useRescanSubmissionFile()
    return (
        <ul className="space-y-1">
            {submission.files
                .filter((file) => file.scan_status === "error")
                .map((file) => (
                    <li key={file.id} className="flex flex-wrap items-center gap-2">
                        <span>
                            <span className="font-medium">Scan failed:</span> {file.filename}
                        </span>
                        {canRescan ? (
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={rescan.isPending}
                                aria-label={`Rescan ${file.filename}`}
                                onClick={() => {
                                    rescan
                                        .mutateAsync({
                                            submissionId: submission.id,
                                            fileId: file.id,
                                            formId: submission.form_id,
                                        })
                                        .then(() => toast.success("Rescan queued"))
                                        .catch((error: unknown) =>
                                            toast.error(errorMessage(error, "Unable to rescan file")),
                                        )
                                }}
                            >
                                Rescan
                            </Button>
                        ) : null}
                    </li>
                ))}
        </ul>
    )
}

function SubmissionMetricCard({
    label,
    value,
}: {
    label: string
    value: number | string
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
    routingReviewSubmissions,
    routingReviewQueueStatus,
    ambiguousSubmissions,
    leadQueueSubmissions,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "pendingSubmissionHistory"
    | "processedSubmissionHistory"
    | "routingReviewSubmissions"
    | "routingReviewQueueStatus"
    | "ambiguousSubmissions"
    | "leadQueueSubmissions"
>) {
    return (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <SubmissionMetricCard label="Pending Applications" value={pendingSubmissionHistory.length} />
            <SubmissionMetricCard label="Processed Outcomes" value={processedSubmissionHistory.length} />
            <SubmissionMetricCard
                label="Routing Review"
                value={routingReviewQueueStatus === "ready" ? routingReviewSubmissions.length : "—"}
            />
            <SubmissionMetricCard label="Ambiguous Queue" value={ambiguousSubmissions.length} />
            <SubmissionMetricCard label="Lead Queue" value={leadQueueSubmissions.length} />
        </div>
    )
}

function SubmissionIdentityGrid({
    identity,
    submission,
}: {
    identity: SubmissionIdentity
    submission: FormSubmissionRead
}) {
    const isDonor = isDonorFormLeadKind(submission.lead_kind)
    return (
        <div className="flex items-start gap-3">
            <DonorProfilePhotoPreview submission={submission} />
            <div className="grid min-w-0 flex-1 gap-1 sm:grid-cols-2">
                <div><span className="font-medium">Name:</span> {identity.fullName}</div>
                {isDonor ? (
                    <div><span className="font-medium">Education:</span> {identity.education}</div>
                ) : (
                    <div><span className="font-medium">DOB:</span> {identity.dateOfBirth}</div>
                )}
                <div><span className="font-medium">Phone:</span> {identity.phone}</div>
                <div><span className="font-medium">Email:</span> {identity.email}</div>
                {isDonor ? (
                    <div><span className="font-medium">State:</span> {identity.state}</div>
                ) : null}
            </div>
        </div>
    )
}

const ROUTING_MATCH_OUTCOME_MESSAGES: Partial<Record<ResolveSubmissionMatchResponse["outcome"], string>> = {
    linked: "Submission linked",
    lead_created: "Intake lead created",
    ambiguous_review: "Submission moved to the ambiguous match queue",
    routing_review: "No match found",
}

function RoutingReviewRow({
    submission,
    canReviewRouting,
    readAnswerValue,
    formatSubmissionDateTime,
}: {
    submission: FormSubmissionRead
    canReviewRouting: (submission: FormSubmissionRead, action: RoutingReviewAction) => boolean
    readAnswerValue: SubmissionIdentityReader
    formatSubmissionDateTime: (isoString: string) => string
}) {
    const runMatch = useRunSubmissionRoutingMatch()
    const createLead = useCreateSubmissionRoutingLead()
    const dismiss = useDismissSubmissionRoutingReview()
    const variables = { submissionId: submission.id, formId: submission.form_id }
    const isPending = runMatch.isPending || createLead.isPending || dismiss.isPending
    const canReviewSubmission = canReviewRouting(submission, "review")
    const applicant = readAnswerValue(submission, ["full_name", "name"])
    const step = submission.routing_review_step

    const perform = async (
        action: () => Promise<ResolveSubmissionMatchResponse>,
        successMessage: (result: ResolveSubmissionMatchResponse) => string,
        errorFallback: string,
    ) => {
        try {
            const result = await action()
            toast.success(successMessage(result))
        } catch (error) {
            toast.error(errorMessage(error, errorFallback))
        }
    }

    return (
        <TableRow>
            <TableCell className="font-medium">{applicant}</TableCell>
            <TableCell className="whitespace-nowrap">{formatSubmissionDateTime(submission.submitted_at)}</TableCell>
            <TableCell>
                <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">
                    {getRoutingReviewStepLabel(step)}
                </Badge>
            </TableCell>
            <TableCell>
                <div className="flex flex-wrap justify-end gap-2">
                    {step === "match" ? (
                        <Button
                            type="button"
                            size="sm"
                            disabled={isPending || !canReviewSubmission}
                            aria-label={`Run match for ${applicant}`}
                            onClick={() =>
                                void perform(
                                    () => runMatch.mutateAsync(variables),
                                    (result) => ROUTING_MATCH_OUTCOME_MESSAGES[result.outcome] ?? "Match check complete",
                                    "Unable to run match",
                                )
                            }
                        >
                            Run match
                        </Button>
                    ) : null}
                    {step === "create_lead" ? (
                        <Button
                            type="button"
                            size="sm"
                            disabled={isPending || !canReviewRouting(submission, "create_lead")}
                            aria-label={`Create lead for ${applicant}`}
                            onClick={() =>
                                void perform(
                                    () => createLead.mutateAsync(variables),
                                    () => "Intake lead created",
                                    "Unable to create intake lead",
                                )
                            }
                        >
                            Create lead
                        </Button>
                    ) : null}
                    <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isPending || !canReviewSubmission}
                        aria-label={`Dismiss routing review for ${applicant}`}
                        onClick={() =>
                            void perform(
                                () => dismiss.mutateAsync(variables),
                                () => "Routing review dismissed",
                                "Unable to dismiss routing review",
                            )
                        }
                    >
                        Dismiss
                    </Button>
                </div>
            </TableCell>
        </TableRow>
    )
}

const canReviewAnyRouting = () => true

function RoutingReviewQueueCard({
    routingReviewSubmissions,
    routingReviewQueueStatus,
    isRoutingReviewRetrying,
    onRetryRoutingReview,
    canReviewRouting = canReviewAnyRouting,
    readAnswerValue,
    formatSubmissionDateTime,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "routingReviewSubmissions"
    | "routingReviewQueueStatus"
    | "isRoutingReviewRetrying"
    | "onRetryRoutingReview"
    | "canReviewRouting"
    | "readAnswerValue"
    | "formatSubmissionDateTime"
>) {
    return (
        <Card>
            <CardContent className="space-y-4 p-5">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold">Routing Review</h3>
                    {routingReviewQueueStatus === "ready" ? (
                        <Badge variant="outline">{routingReviewSubmissions.length}</Badge>
                    ) : null}
                </div>
                {routingReviewQueueStatus === "loading" ? (
                    <p className="text-sm text-stone-500" role="status">Loading routing review…</p>
                ) : routingReviewQueueStatus === "error" ? (
                    <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
                        <p>Unable to load routing review.</p>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isRoutingReviewRetrying}
                            onClick={onRetryRoutingReview}
                        >
                            Retry
                        </Button>
                    </div>
                ) : routingReviewSubmissions.length === 0 ? (
                    <p className="text-sm text-stone-500">No submissions waiting for routing review.</p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Applicant</TableHead>
                                <TableHead>Submitted</TableHead>
                                <TableHead>Waiting on</TableHead>
                                <TableHead>
                                    <span className="sr-only">Actions</span>
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {routingReviewSubmissions.map((submission) => (
                                <RoutingReviewRow
                                    key={submission.id}
                                    submission={submission}
                                    canReviewRouting={canReviewRouting}
                                    readAnswerValue={readAnswerValue}
                                    formatSubmissionDateTime={formatSubmissionDateTime}
                                />
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function AmbiguousSubmissionCard({
    submission,
    isSelected,
    canEditSubject,
    readAnswerValue,
    resolveSubmissionMatchPending,
    onSelectQueueSubmission,
    onResolveSubmissionToLead,
}: {
    submission: FormSubmissionRead
    isSelected: boolean
    canEditSubject: boolean
    readAnswerValue: SubmissionIdentityReader
    resolveSubmissionMatchPending: boolean
    onSelectQueueSubmission: (submissionId: string | null) => void
    onResolveSubmissionToLead: (submissionId: string) => Promise<void> | void
}) {
    const identity = readSubmissionIdentity(submission, readAnswerValue)

    return (
        <div className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm">
            <Badge variant="outline">{FORM_LEAD_KIND_LABELS[submission.lead_kind]}</Badge>
            <SubmissionIdentityGrid identity={identity} submission={submission} />
            <MatchReason submission={submission} />
            <div className="flex flex-wrap gap-2">
                <Button
                    type="button"
                    size="sm"
                    variant={isSelected ? "default" : "outline"}
                    disabled={
                        isDonorFormLeadKind(submission.lead_kind) &&
                        resolveSubmissionMatchPending
                    }
                    onClick={() => {
                        if (isDonorFormLeadKind(submission.lead_kind)) {
                            void onResolveSubmissionToLead(submission.id)
                            return
                        }
                        onSelectQueueSubmission(isSelected ? null : submission.id)
                    }}
                >
                    {isDonorFormLeadKind(submission.lead_kind)
                        ? "Create Intake Lead"
                        : isSelected
                            ? "Hide Candidates"
                            : "Review Candidates"}
                </Button>
                {!isDonorFormLeadKind(submission.lead_kind) ? <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={resolveSubmissionMatchPending}
                    onClick={() => void onResolveSubmissionToLead(submission.id)}
                >
                    Keep As Lead
                </Button>
                : null}
            </div>
            {canEditSubject && isPendingDonorReview(submission) ? (
                <DonorReviewControls submission={submission} />
            ) : null}
        </div>
    )
}

function AmbiguousMatchQueueCard({
    canEditSubject,
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
> & {
    canEditSubject: SubjectEditCheck
}) {
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
                                canEditSubject={canEditSubject(submission)}
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
    canPromoteLead,
}: {
    submission: FormSubmissionRead
    readAnswerValue: SubmissionIdentityReader
    promoteIntakeLeadPending: boolean
    onPromoteLeadFromSubmission: (submission: FormSubmissionRead) => Promise<void> | void
    canPromoteLead?: ((submission: FormSubmissionRead) => boolean) | undefined
}) {
    const identity = readSubmissionIdentity(submission, readAnswerValue)

    return (
        <div className="space-y-2 rounded-lg border border-stone-200 p-3 text-sm">
            <Badge variant="outline">{FORM_LEAD_KIND_LABELS[submission.lead_kind]}</Badge>
            <SubmissionIdentityGrid identity={identity} submission={submission} />
            <div className="flex flex-wrap gap-2">
                <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={promoteIntakeLeadPending || !submission.intake_lead_id || (canPromoteLead ? !canPromoteLead(submission) : false)}
                    onClick={() => void onPromoteLeadFromSubmission(submission)}
                >
                    {isDonorFormLeadKind(submission.lead_kind)
                        ? `Promote to ${FORM_LEAD_KIND_LABELS[submission.lead_kind]}`
                        : "Promote Lead"}
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
    canPromoteLead,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "leadQueueSubmissions"
    | "readAnswerValue"
    | "promoteIntakeLeadPending"
    | "onPromoteLeadFromSubmission"
    | "canPromoteLead"
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
                                canPromoteLead={canPromoteLead}
                            />
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function SubmissionReviewQueues({
    canEditSubject,
    canReviewRouting,
    formId,
    routingReviewSubmissions,
    routingReviewQueueStatus,
    isRoutingReviewRetrying,
    onRetryRoutingReview,
    ambiguousSubmissions,
    leadQueueSubmissions,
    selectedQueueSubmissionId,
    readAnswerValue,
    formatSubmissionDateTime,
    resolveSubmissionMatchPending,
    promoteIntakeLeadPending,
    onSelectQueueSubmission,
    onResolveSubmissionToLead,
    onPromoteLeadFromSubmission,
    canPromoteLead,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    | "formId"
    | "canReviewRouting"
    | "routingReviewSubmissions"
    | "routingReviewQueueStatus"
    | "isRoutingReviewRetrying"
    | "onRetryRoutingReview"
    | "formatSubmissionDateTime"
    | "ambiguousSubmissions"
    | "leadQueueSubmissions"
    | "selectedQueueSubmissionId"
    | "readAnswerValue"
    | "resolveSubmissionMatchPending"
    | "promoteIntakeLeadPending"
    | "onSelectQueueSubmission"
    | "onResolveSubmissionToLead"
    | "onPromoteLeadFromSubmission"
    | "canPromoteLead"
> & {
    canEditSubject: SubjectEditCheck
}) {
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
        <div className="space-y-6">
            <RoutingReviewQueueCard
                routingReviewSubmissions={routingReviewSubmissions}
                routingReviewQueueStatus={routingReviewQueueStatus}
                isRoutingReviewRetrying={isRoutingReviewRetrying}
                onRetryRoutingReview={onRetryRoutingReview}
                canReviewRouting={canReviewRouting}
                readAnswerValue={readAnswerValue}
                formatSubmissionDateTime={formatSubmissionDateTime}
            />
            <div className="grid gap-6 xl:grid-cols-2">
                <AmbiguousMatchQueueCard
                    canEditSubject={canEditSubject}
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
                    canPromoteLead={canPromoteLead}
                />
            </div>
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
    const isDonor = isDonorFormLeadKind(submission.lead_kind)
    const state = readAnswerValue(submission, ["state", "residence_state"])
    const education = readAnswerValue(submission, ["education", "education_level"])

    return (
        <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
            <div><span className="font-medium">Name:</span> {fullName}</div>
            <div><span className="font-medium">Email:</span> {email}</div>
            <div><span className="font-medium">Phone:</span> {phone}</div>
            {isDonor ? (
                <div><span className="font-medium">Education:</span> {education}</div>
            ) : null}
            {isDonor ? (
                <div><span className="font-medium">State:</span> {state}</div>
            ) : null}
            <div>
                <span className="font-medium">Submitted:</span>{" "}
                {formatSubmissionDateTime(submission.submitted_at)}
            </div>
            <div>
                <span className="font-medium">Record:</span>{" "}
                {submission.donor_id && submission.donor_number ? (
                    <Link
                        href={`/donors/${submission.donor_id}` as Route}
                        aria-label={`Open donor ${submission.donor_number}`}
                        className="text-primary hover:underline"
                    >
                        {submission.donor_number}
                    </Link>
                ) : submission.donor_id ? (
                    <span className="text-muted-foreground">Donor record unavailable</span>
                ) : submission.surrogate_id ? (
                    <Link
                        href={`/surrogates/${submission.surrogate_id}` as Route}
                        aria-label={`Open surrogate ${submission.surrogate_id}`}
                        className="text-primary hover:underline"
                    >
                        {submission.surrogate_id}
                    </Link>
                ) : "—"}
            </div>
            <div>
                <span className="font-medium">Lead:</span>{" "}
                {submission.intake_lead_id ? submission.intake_lead_id : "—"}
            </div>
            <MatchReason submission={submission} />
            {isDonor ? (
                <div className="sm:col-span-2 lg:col-span-3">
                    <DonorProfilePhotoPreview submission={submission} />
                </div>
            ) : null}
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
            <Badge variant="outline">{FORM_LEAD_KIND_LABELS[submission.lead_kind]}</Badge>
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
    canReview = true,
    submission,
    retrySubmissionMatchPending,
    onSelectQueueSubmission,
    onRetrySubmissionMatch,
}: Pick<
    AutomationFormSubmissionsPanelProps,
    "canReview" |
    "retrySubmissionMatchPending" | "onSelectQueueSubmission" | "onRetrySubmissionMatch"
> & {
    submission: FormSubmissionRead
}) {
    if (!canReview) return null
    const canReviewCandidates =
        submission.source_mode === "shared" &&
        submission.match_status === "ambiguous_review" &&
        !isDonorFormLeadKind(submission.lead_kind)
    const canReprocess =
        submission.source_mode === "shared" &&
        (!isDonorFormLeadKind(submission.lead_kind) || !submission.donor_id)
    const isDonor = isDonorFormLeadKind(submission.lead_kind)

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
                                unlinkSurrogate: isDonor ? false : Boolean(submission.surrogate_id),
                                rerunAutoMatch: true,
                                ...(isDonor ? { createIntakeLeadIfUnmatched: true } : {}),
                            },
                            isDonor ? "Submission reprocessed" : "Auto-match re-run complete",
                        )
                    }
                >
                    {isDonor ? "Reprocess" : "Re-run Auto-Match"}
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
                                unlinkSurrogate: isDonor ? false : Boolean(submission.surrogate_id),
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
    canReview = true,
    canEditSubject,
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
    "canReview"
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
    canEditSubject: boolean
    submission: FormSubmissionRead
}) {
    const hasFailedScan = submission.files.some((file) => file.scan_status === "error")
    // Ambiguous donor applications show these controls in the review queue instead.
    const showDonorControls =
        canReview &&
        canEditSubject &&
        isPendingDonorReview(submission) &&
        submission.match_status !== "ambiguous_review"

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
            {hasFailedScan ? (
                <FailedScanFiles submission={submission} canRescan={canReview && canEditSubject} />
            ) : null}
            <SubmissionHistoryActions
                canReview={canReview}
                submission={submission}
                retrySubmissionMatchPending={retrySubmissionMatchPending}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onRetrySubmissionMatch={onRetrySubmissionMatch}
            />
            {showDonorControls ? <DonorReviewControls submission={submission} align="end" /> : null}
        </div>
    )
}

function SubmissionHistoryCard({
    canReview = true,
    canEditSubject,
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
    "canReview"
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
> & {
    canEditSubject: SubjectEditCheck
}) {
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
                                canReview={canReview}
                                canEditSubject={canEditSubject(submission)}
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
                                    <p className="text-xs text-stone-500">{matchReasonLabel(candidate.reason)}</p>
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

// Callers that do not pass subject access get no donor review or rescan controls.
const canEditNoSubject: SubjectEditCheck = () => false

function isOpenForReview(submission: FormSubmissionRead) {
    return submission.status !== "rejected"
}

export function AutomationFormSubmissionsPanel({
    canReview = true,
    canEditSubject = canEditNoSubject,
    canReviewRouting,
    formId,
    pendingSubmissionHistory,
    processedSubmissionHistory,
    routingReviewSubmissions,
    routingReviewQueueStatus,
    isRoutingReviewRetrying,
    onRetryRoutingReview,
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
    onSubmissionHistoryFilterChange,
    onSelectQueueSubmission,
    onManualSurrogateIdChange,
    onResolveReviewNotesChange,
    onLinkByManualSurrogateId,
    onResolveSubmissionToSurrogate,
    onResolveSubmissionToLead,
    onRetrySubmissionMatch,
    onPromoteLeadFromSubmission,
    canPromoteLead,
}: AutomationFormSubmissionsPanelProps) {
    const openRoutingReviewSubmissions = routingReviewSubmissions.filter(isOpenForReview)
    const openAmbiguousSubmissions = ambiguousSubmissions.filter(isOpenForReview)
    const openLeadQueueSubmissions = leadQueueSubmissions.filter(isOpenForReview)
    return (
        <div className="mx-auto max-w-6xl space-y-6">
            <SubmissionMetricsGrid
                pendingSubmissionHistory={pendingSubmissionHistory}
                processedSubmissionHistory={processedSubmissionHistory}
                routingReviewSubmissions={openRoutingReviewSubmissions}
                routingReviewQueueStatus={routingReviewQueueStatus}
                ambiguousSubmissions={openAmbiguousSubmissions}
                leadQueueSubmissions={openLeadQueueSubmissions}
            />
            {canReview && <SubmissionReviewQueues
                canEditSubject={canEditSubject}
                canReviewRouting={canReviewRouting}
                formId={formId}
                routingReviewSubmissions={openRoutingReviewSubmissions}
                routingReviewQueueStatus={routingReviewQueueStatus}
                isRoutingReviewRetrying={isRoutingReviewRetrying}
                onRetryRoutingReview={onRetryRoutingReview}
                formatSubmissionDateTime={formatSubmissionDateTime}
                ambiguousSubmissions={openAmbiguousSubmissions}
                leadQueueSubmissions={openLeadQueueSubmissions}
                selectedQueueSubmissionId={selectedQueueSubmissionId}
                readAnswerValue={readAnswerValue}
                resolveSubmissionMatchPending={resolveSubmissionMatchPending}
                promoteIntakeLeadPending={promoteIntakeLeadPending}
                onSelectQueueSubmission={onSelectQueueSubmission}
                onResolveSubmissionToLead={onResolveSubmissionToLead}
                onPromoteLeadFromSubmission={onPromoteLeadFromSubmission}
                canPromoteLead={canPromoteLead}
            />}
            <SubmissionHistoryCard
                canReview={canReview}
                canEditSubject={canEditSubject}
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
            {canReview && <SubmissionCandidateReviewCard
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
            />}
        </div>
    )
}
