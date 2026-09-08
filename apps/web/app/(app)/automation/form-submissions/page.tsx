"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { listSubmissionReviewForms } from "@/lib/api/forms"
import { useFormSubmissions, usePromoteIntakeLead, useResolveSubmissionMatch, useRetrySubmissionMatch, useSubmissionMatchCandidates } from "@/lib/hooks/use-forms"
import { AutomationFormSubmissionsPanel } from "@/components/forms/builder/AutomationFormSubmissionsPanel"
import * as presentation from "@/lib/forms/submission-presentation"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "@/components/ui/toast"

export default function FormSubmissionsPage() {
    const {user} = useAuth()
    const access = useEffectivePermissions(user?.user_id ?? null)
    if (access.isLoading) return <div className="p-6"><Skeleton className="h-48" /></div>
    if (access.isError) return <div role="alert" className="space-y-3 p-6"><p>Unable to load permissions.</p><Button variant="outline" onClick={() => {void access.refetch()}}>Retry</Button></div>
    const permissions = access.data?.permissions ?? []
    const v2 = (access.data?.policy_version ?? 1) >= 2
    if (!permissions.includes(v2 ? "view_form_submissions" : "manage_forms")) return <div className="p-6"><h1 className="text-xl font-semibold">Form submissions unavailable</h1></div>
    return <SubmissionWorkspace canReview={permissions.includes(v2 ? "review_form_submissions" : "manage_forms")} />
}

function SubmissionWorkspace({canReview}: {canReview: boolean}) {
    const [chosenForm, setChosenForm] = useState<string | null>(null)
    const forms = useQuery({queryKey: ["forms", "submission-review"], queryFn: listSubmissionReviewForms})
    const formId = forms.data?.find(form => form.id === chosenForm)?.id ?? forms.data?.[0]?.id ?? null
    return <div className="space-y-6 p-6">
        <div className="flex flex-wrap items-center justify-between gap-4"><h1 className="text-2xl font-semibold">Form Submissions</h1>
            <Select value={formId} onValueChange={setChosenForm} disabled={forms.isLoading || !forms.data?.length}>
                <SelectTrigger className="w-72" aria-label="Form"><SelectValue>{() => forms.data?.find(form => form.id === formId)?.name ?? "Select form"}</SelectValue></SelectTrigger>
                <SelectContent>{forms.data?.map(form => <SelectItem key={form.id} value={form.id}>{form.name}</SelectItem>)}</SelectContent>
            </Select>
        </div>
        {forms.isLoading ? <Skeleton className="h-48" /> : forms.isError ? <div role="alert" className="space-y-2"><p>Unable to load submission forms.</p><Button variant="outline" onClick={() => {void forms.refetch()}}>Retry</Button></div> : formId ? <SubmissionQueue key={formId} formId={formId} canReview={canReview} /> : <p className="text-muted-foreground">No submissions available</p>}
    </div>
}

function SubmissionQueue({formId, canReview}: {formId: string; canReview: boolean}) {
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
    if (submissions.isError) return <div role="alert" className="space-y-2"><p>Unable to load submissions.</p><Button variant="outline" onClick={() => {void submissions.refetch()}}>Retry</Button></div>
    return <>
        {candidates.isError && <div role="alert" className="flex items-center gap-3"><p>Unable to load matching records.</p><Button variant="outline" onClick={() => {void candidates.refetch()}}>Retry matches</Button></div>}
        <AutomationFormSubmissionsPanel {...presentation}
            canReview={canReview} showWorkflowApprovals={false} formId={formId}
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
            onPromoteLeadFromSubmission={submission => {if (submission.intake_lead_id) return perform(() => promote.mutateAsync({leadId: submission.intake_lead_id!}), "Intake record created")}}
        />
        {rows.length === limit && limit < 1000 && <Button variant="outline" onClick={() => setLimit(value => Math.min(1000, value + 100))}>Load more</Button>}
    </>
}
