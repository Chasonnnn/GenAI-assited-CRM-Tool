"use client"

import { Suspense, useState, type ReactNode } from "react"
import { useSearchParams } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { canCreateIntakeRecord } from "@/lib/forms/record-creation-access"
import { isDonorFormLeadKind } from "@/lib/forms/form-lead-kind"
import type { FormSubmissionRead } from "@/lib/api/forms"
import { listSubmissionReviewForms } from "@/lib/api/forms"
import { useFormSubmissions, usePromoteIntakeLead, useResolveSubmissionMatch, useRetrySubmissionMatch, useSubmissionMatchCandidates } from "@/lib/hooks/use-forms"
import { AutomationFormSubmissionsPanel } from "@/components/forms/builder/AutomationFormSubmissionsPanel"
import * as presentation from "@/lib/forms/submission-presentation"
import { FileTextIcon } from "lucide-react"
import { EmptyState } from "@/components/empty-state"
import { LoadErrorState, PermissionDeniedState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "@/components/ui/toast"

const FORM_SUBMISSIONS_DENIED = {
    title: "No access to Form Submissions",
    description: "Ask an admin to update your role.",
    secondaryHref: "/dashboard",
} as const

function FormSubmissionsShell({actions, children}: {actions?: ReactNode; children: ReactNode}) {
    return <div className="flex min-h-screen flex-col">
        <PageHeader title="Form Submissions" actions={actions} />
        {children}
    </div>
}

export default function FormSubmissionsPage() {
    const {user} = useAuth()
    const access = useEffectivePermissions(user?.user_id ?? null)
    if (access.isLoading) return <FormSubmissionsShell><div className="p-6"><Skeleton className="h-48" /></div></FormSubmissionsShell>
    if (access.isError) return <FormSubmissionsShell><LoadErrorState title="Couldn't load permissions" onRetry={() => {void access.refetch()}} isRetrying={access.isFetching} /></FormSubmissionsShell>
    const permissions = access.data?.permissions ?? []
    const v2 = (access.data?.policy_version ?? 1) >= 2
    if (!permissions.includes(v2 ? "view_form_submissions" : "manage_forms")) return <FormSubmissionsShell><PermissionDeniedState {...FORM_SUBMISSIONS_DENIED} /></FormSubmissionsShell>
    return <Suspense fallback={<FormSubmissionsShell><div className="p-6"><Skeleton className="h-48" /></div></FormSubmissionsShell>}>
        <SubmissionWorkspace
            canPromoteLead={submission => canCreateIntakeRecord(access.data, submission.lead_kind)}
            canEditSubject={submission => permissions.includes(isDonorFormLeadKind(submission.lead_kind) ? "edit_donors" : "edit_surrogates")}
            canReview={permissions.includes(v2 ? "review_form_submissions" : "manage_forms")} />
    </Suspense>
}

type SubmissionAccess = {
    canReview: boolean
    canPromoteLead: (submission: FormSubmissionRead) => boolean
    canEditSubject: (submission: FormSubmissionRead) => boolean
}

function SubmissionWorkspace({canReview, canPromoteLead, canEditSubject}: SubmissionAccess) {
    const searchParams = useSearchParams()
    const [chosenForm, setChosenForm] = useState<string | null>(() => searchParams.get("form"))
    const forms = useQuery({queryKey: ["forms", "submission-review"], queryFn: listSubmissionReviewForms})
    const formId = forms.data?.find(form => form.id === chosenForm)?.id ?? forms.data?.[0]?.id ?? null
    const formSelect = <Select value={formId} onValueChange={setChosenForm} disabled={forms.isLoading || !forms.data?.length}>
        <SelectTrigger className="w-full sm:w-72" aria-label="Form"><SelectValue>{() => forms.data?.find(form => form.id === formId)?.name ?? "Select form"}</SelectValue></SelectTrigger>
        <SelectContent>{forms.data?.map(form => <SelectItem key={form.id} value={form.id}>{form.name}</SelectItem>)}</SelectContent>
    </Select>
    if (forms.isError) return <FormSubmissionsShell actions={formSelect}><LoadErrorState title="Couldn't load submission forms" onRetry={() => {void forms.refetch()}} isRetrying={forms.isFetching} /></FormSubmissionsShell>
    if (!forms.isLoading && !formId) return <FormSubmissionsShell actions={formSelect}><EmptyState icon={FileTextIcon} title="No submissions available" /></FormSubmissionsShell>
    return <FormSubmissionsShell actions={formSelect}>
        <div className="flex-1 space-y-6 p-6">
            {forms.isLoading || !formId ? <Skeleton className="h-48" /> : <SubmissionQueue key={formId} formId={formId} canReview={canReview} canPromoteLead={canPromoteLead} canEditSubject={canEditSubject} />}
        </div>
    </FormSubmissionsShell>
}

function SubmissionQueue({formId, canReview, canPromoteLead, canEditSubject}: SubmissionAccess & {formId: string}) {
    const [filter, setFilter] = useState<"all" | "pending" | "processed">("all")
    const [selected, setSelected] = useState<string | null>(null)
    const [manualId, setManualId] = useState("")
    const [notes, setNotes] = useState("")
    const [limit, setLimit] = useState(100)
    const submissions = useFormSubmissions(formId, {limit})
    const candidates = useSubmissionMatchCandidates(canReview ? selected : null)
    const resolve = useResolveSubmissionMatch()
    const retry = useRetrySubmissionMatch()
    const promote = usePromoteIntakeLead()
    const rows = submissions.data ?? []
    const processed = rows.filter(row => row.match_status === "linked" || row.match_status === "lead_created")
    const pending = rows.filter(row => row.match_status !== "linked" && row.match_status !== "lead_created")
    const perform = async (action: () => Promise<unknown>, message: string) => {
        if (!canReview) return
        try {
            await action(); setSelected(null); setManualId(""); setNotes("")
            await submissions.refetch(); toast.success(message)
        } catch (error) {toast.error(error instanceof Error ? error.message : "Unable to update submission")}
    }
    const link = (submissionId: string, surrogateId: string) => perform(() => resolve.mutateAsync({submissionId, payload: {surrogate_id: surrogateId, create_intake_lead: false, review_notes: notes.trim() || null}}), "Submission linked")
    if (submissions.isError) return <LoadErrorState title="Couldn't load submissions" onRetry={() => {void submissions.refetch()}} isRetrying={submissions.isFetching} />
    return <>
        {candidates.isError && <div role="alert" className="flex items-center gap-3"><p>Unable to load matching records.</p><Button variant="outline" onClick={() => {void candidates.refetch()}}>Retry matches</Button></div>}
        <AutomationFormSubmissionsPanel {...presentation}
            canReview={canReview} canPromoteLead={canPromoteLead} canEditSubject={canEditSubject} showWorkflowApprovals={false} formId={formId}
            pendingSubmissionHistory={pending} processedSubmissionHistory={processed}
            ambiguousSubmissions={rows.filter(row => row.match_status === "ambiguous_review")}
            leadQueueSubmissions={rows.filter(row => row.match_status === "lead_created" && !row.surrogate_id && !row.donor_id)}
            visibleSubmissionHistory={filter === "pending" ? pending : filter === "processed" ? processed : rows}
            submissionHistoryFilter={filter} selectedQueueSubmissionId={selected}
            selectedMatchCandidates={candidates.data ?? []} isSubmissionHistoryLoading={submissions.isLoading}
            isMatchCandidatesLoading={candidates.isLoading} retrySubmissionMatchPending={retry.isPending}
            resolveSubmissionMatchPending={resolve.isPending} promoteIntakeLeadPending={promote.isPending}
            manualSurrogateId={manualId} resolveReviewNotes={notes}
            onOpenApprovalQueue={() => {}} onSubmissionHistoryFilterChange={setFilter}
            onSelectQueueSubmission={setSelected} onManualSurrogateIdChange={setManualId}
            onResolveReviewNotesChange={setNotes}
            onLinkByManualSurrogateId={() => {if (selected && manualId.trim()) return link(selected, manualId.trim())}}
            onResolveSubmissionToSurrogate={link}
            onResolveSubmissionToLead={submissionId => perform(() => resolve.mutateAsync({submissionId, payload: {create_intake_lead: true, review_notes: notes.trim() || null}}), "Submission moved to intake")}
            onRetrySubmissionMatch={(submission, options, message) => perform(() => retry.mutateAsync({submissionId: submission.id, payload: {unlink_surrogate: options.unlinkSurrogate ?? false, unlink_intake_lead: options.unlinkIntakeLead ?? false, rerun_auto_match: options.rerunAutoMatch ?? true, create_intake_lead_if_unmatched: options.createIntakeLeadIfUnmatched ?? false, review_notes: notes.trim() || null}}), message)}
            onPromoteLeadFromSubmission={submission => {if (submission.intake_lead_id && canPromoteLead(submission)) return perform(() => promote.mutateAsync({leadId: submission.intake_lead_id!}), "Intake record created")}}
        />
        {rows.length === limit && limit < 1000 && <Button variant="outline" onClick={() => setLimit(value => Math.min(1000, value + 100))}>Load more</Button>}
    </>
}
