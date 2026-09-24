"use client"

import { useState } from "react"
import { CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useActivatePolicy, useAvailablePermissions, useMembers, usePolicyConfiguration, usePreviewPolicy } from "@/lib/hooks/use-permissions"
import type { PolicyChanges } from "@/lib/api/permissions"
import { ChoiceField, PermissionError, PermissionLoading, ROLE_LABELS } from "./permission-controls"
import { PermissionMigrationReview } from "./permission-migration-review"

export function PermissionPolicyReview() {
    const policy = usePolicyConfiguration()
    const members = useMembers(true)
    const available = useAvailablePermissions()
    const preview = usePreviewPolicy()
    const activate = useActivatePolicy()
    const [changes, setChanges] = useState<PolicyChanges>({})
    const [reviewedChanges, setReviewedChanges] = useState<string | null>(null)
    const [scopeChanged, setScopeChanged] = useState(false)
    const [confirmOpen, setConfirmOpen] = useState(false)
    const serialized = JSON.stringify(changes)
    const fresh = serialized === reviewedChanges && !scopeChanged
    const memberName = (userId: string) => { const member = members.data?.find((item) => item.user_id === userId); return member?.display_name || member?.email || "Former member" }
    const permissionName = (key: string) => available.data?.find((item) => item.key === key)?.label || key.replaceAll("_", " ")
    const generate = async () => {
        try { await preview.mutateAsync(changes); setReviewedChanges(serialized); setScopeChanged(false); activate.reset() } catch { setReviewedChanges(null) }
    }
    if (policy.isLoading || members.isLoading || available.isLoading) return <PermissionLoading />
    if (policy.error || members.error || available.error) return <PermissionError error={policy.error || members.error || available.error} retry={() => { void policy.refetch(); void members.refetch(); void available.refetch() }} />
    if (policy.data?.version === 2 || activate.isSuccess) return <div role="status" className="flex items-center gap-3 rounded-2xl border bg-card p-8"><CheckCircle2 className="size-6 text-emerald-600" /><h2 className="text-xl font-semibold">Permission upgrade active</h2></div>
    const review = preview.data
    const hasChanges = review?.members.some((member) => member.gained.length || member.lost.length)
    return <div className="mx-auto max-w-5xl space-y-6">
        <section className="rounded-2xl border bg-card p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-4"><h2 className="text-xl font-semibold">Review permission upgrade</h2><Button variant="outline" disabled={preview.isPending || activate.isPending} onClick={() => void generate()}>{preview.isPending ? "Preparing preview…" : review ? "Refresh preview" : "Generate preview"}</Button></div>
            <p className="mt-4 max-w-3xl text-sm text-muted-foreground">Activation applies the reviewed role permissions, replaces individual revokes, and pauses the selected legacy automation. Current access remains in place until activation.</p>
            {preview.error && <div className="mt-5"><PermissionError error={preview.error} /></div>}
        </section>
        {review && <>
            <section className="rounded-2xl border bg-card p-6 sm:p-8"><h3 className="mb-5 font-semibold">Access changes</h3>
                {!hasChanges && <p className="text-sm text-muted-foreground">No action permission changes.</p>}
                <div className="space-y-3">{review.members.filter((member) => member.gained.length || member.lost.length).map((member) => <details key={member.membership_id} className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">{memberName(member.user_id)} <span className="ml-2 font-normal text-muted-foreground">{ROLE_LABELS[member.role] || member.role} · +{member.gained.length} / −{member.lost.length}</span></summary><div className="mt-4 grid gap-4 sm:grid-cols-2"><div><h4 className="mb-2 text-xs font-semibold text-emerald-700 dark:text-emerald-400">Added</h4><ul className="space-y-1 text-sm">{member.gained.map((key) => <li key={key}>{permissionName(key)}</li>)}</ul></div><div><h4 className="mb-2 text-xs font-semibold text-destructive">Removed</h4><ul className="space-y-1 text-sm">{member.lost.map((key) => <li key={key}>{permissionName(key)}</li>)}</ul></div></div></details>)}</div>
            </section>
            {review.revokes.length > 0 && <section className="space-y-4 rounded-2xl border bg-card p-6 sm:p-8"><h3 className="font-semibold">Individual revoke resolutions</h3>{review.revokes.map((revoke) => <div key={revoke.override_id} className="grid items-end gap-3 rounded-xl border p-4 sm:grid-cols-2"><p className="text-sm font-medium">{memberName(revoke.user_id)}<span className="mt-1 block font-normal text-muted-foreground">{permissionName(revoke.permission)}</span></p><ChoiceField label="Resolution" value={changes.revoke_resolutions?.find((item) => item.override_id === revoke.override_id)?.action ?? ""} options={revoke.can_deny_for_role ? { remove: "Remove individual revoke", deny_for_role: `Remove from all ${ROLE_LABELS[revoke.role || ""] || revoke.role} members` } : { remove: "Remove individual revoke" }} onChange={(action) => setChanges((previous) => ({ ...previous, revoke_resolutions: [...(previous.revoke_resolutions ?? []).filter((item) => item.override_id !== revoke.override_id), { override_id: revoke.override_id, action }] }))} disabled={preview.isPending || activate.isPending} /></div>)}</section>}
            <div className="rounded-2xl border bg-card p-6 sm:p-8"><PermissionMigrationReview review={review.scope_review} members={members.data ?? []} onResolved={() => { setScopeChanged(true); setReviewedChanges(null) }} /></div>
            {review.execution_review.length > 0 && <section className="space-y-4 rounded-2xl border bg-card p-6 sm:p-8"><h3 className="font-semibold">Legacy automation</h3><p className="text-sm text-muted-foreground">These items require a pause during activation. An authorized member can review and restart them afterwards.</p>{review.execution_review.map((item) => <label key={`${item.item_type}:${item.id}`} className="flex items-center gap-3 rounded-xl border p-4 text-sm"><Checkbox checked={changes.execution_resolutions?.some((resolution) => resolution.id === item.id && resolution.item_type === item.item_type) ?? false} disabled={preview.isPending || activate.isPending} onCheckedChange={(checked) => setChanges((previous) => ({ ...previous, execution_resolutions: [...(previous.execution_resolutions ?? []).filter((resolution) => !(resolution.id === item.id && resolution.item_type === item.item_type)), ...(checked ? [{ item_type: item.item_type, id: item.id, action: "pause" as const }] : [])] }))} /><span><span className="font-medium">Pause {item.name || (item.item_type === "workflow" ? "workflow" : "campaign")}</span><span className="mt-1 block text-xs text-muted-foreground">{item.item_type === "workflow" ? "Workflow" : "Campaign"}{item.unreviewed_execution_ids?.length ? ` · ${item.unreviewed_execution_ids.length} pending executions` : ""}</span></span></label>)}</section>}
            <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-4 rounded-2xl border bg-background/95 p-5 backdrop-blur-sm"><p role="status" className="text-sm">{!fresh ? "Refresh preview to review the latest resolutions." : review.ready ? "All required reviews are complete." : "Resolve the outstanding items before activation."}</p><Button disabled={!fresh || !review.ready || preview.isPending || activate.isPending} onClick={() => setConfirmOpen(true)}>Review activation</Button></div>
        </>}
        <Dialog open={confirmOpen} onOpenChange={(open) => { if (!activate.isPending) setConfirmOpen(open) }}><DialogContent><DialogHeader><DialogTitle>Activate reviewed permissions?</DialogTitle><DialogDescription>The reviewed access changes apply to this organization. Selected legacy automation will be paused.</DialogDescription></DialogHeader>{activate.error && <PermissionError error={activate.error} />}<DialogFooter><Button variant="outline" disabled={activate.isPending} onClick={() => setConfirmOpen(false)}>Back</Button><Button disabled={!review?.ready || !fresh || activate.isPending} onClick={async () => { if (!review) return; try { await activate.mutateAsync({ ...changes, digest: review.digest }); setConfirmOpen(false) } catch { setReviewedChanges(null); setConfirmOpen(false) } }}>{activate.isPending ? "Activating…" : "Activate policy"}</Button></DialogFooter></DialogContent></Dialog>
        {activate.error && !confirmOpen && <PermissionError error={activate.error} />}
    </div>
}
