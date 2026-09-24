"use client"

import { useState } from "react"
import Link from "@/components/app-link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { Member } from "@/lib/api/permissions"
import { reviewHandoff, reviewPoolGrant, type HandoffCandidate, type LegacyPoolGrant, type RecordModule, type RecordScopeRule, type ScopeMigrationReview } from "@/lib/api/record-scopes"
import { useRecordScopeMutation } from "@/lib/hooks/use-record-scopes"
import { ChoiceField, MODULE_LABELS, PermissionError, ScopeFields } from "./permission-controls"

function HandoffReview({ candidate, members, onResolved }: { candidate: HandoffCandidate; members: Member[]; onResolved: () => void }) {
    const [decision, setDecision] = useState<"retain_verified_owner" | "no_verified_owner" | "">("")
    const [owner, setOwner] = useState("")
    const [evidence, setEvidence] = useState("")
    const [phase, setPhase] = useState<"pre_approval" | "post_approval" | "">("")
    const mutation = useRecordScopeMutation<void>(async () => {
        if (!decision) return
        await reviewHandoff(candidate, { decision, ...(decision === "retain_verified_owner" ? { intake_user_id: owner } : {}), evidence_reference: evidence.trim(), ...(phase ? { resolved_phase: phase } : {}) })
    })
    return <div className="space-y-4 rounded-xl border p-4">
        <Link href={`/${candidate.kind === "surrogate" ? "surrogates" : "donors"}/${candidate.record_id}`} className="text-sm font-semibold text-primary underline underline-offset-4" target="_blank" rel="noreferrer">{candidate.record_number || (candidate.kind === "surrogate" ? "Open surrogate" : "Open donor")}</Link>
        <ChoiceField label="Historical Intake owner" value={decision} options={{ retain_verified_owner: "Retain verified Intake access", no_verified_owner: "No verified Intake owner" }} onChange={setDecision} disabled={mutation.isPending} />
        {decision === "retain_verified_owner" && <ChoiceField label="Verified Intake Specialist" value={owner} options={Object.fromEntries(members.filter((member) => member.role === "intake_specialist" && member.is_active !== false).map((member) => [member.user_id, member.display_name || member.email]))} onChange={setOwner} disabled={mutation.isPending} />}
        {candidate.phase_requires_review && <ChoiceField label="Verified approval phase" value={phase} options={{ pre_approval: "Before approval", post_approval: "After approval" }} onChange={setPhase} disabled={mutation.isPending} />}
        <label className="block space-y-2 text-sm font-medium"><span>Evidence reference</span><Input value={evidence} maxLength={500} onChange={(event) => setEvidence(event.target.value)} disabled={mutation.isPending} /></label>
        {mutation.error && <PermissionError error={mutation.error} />}
        <Button size="sm" variant="outline" disabled={mutation.isPending || !decision || !evidence.trim() || (decision === "retain_verified_owner" && !owner) || (!!candidate.phase_requires_review && !phase)} onClick={async () => { try { await mutation.mutateAsync(); onResolved() } catch { /* Preserve form for correction. */ } }}>{mutation.isPending ? "Saving…" : "Save record review"}</Button>
    </div>
}

function PoolGrantReview({ grant, members, onResolved }: { grant: LegacyPoolGrant; members: Member[]; onResolved: () => void }) {
    const [decision, setDecision] = useState<"remove" | "replace_with_scope_addition" | "">("")
    const [module, setModule] = useState<RecordModule>("surrogates")
    const [rule, setRule] = useState<RecordScopeRule>({ assignment: "assigned", phase: "all", stage_ids: [] })
    const label = (id: string) => { const member = members.find((item) => item.user_id === id); return member?.display_name || member?.email || "Former member" }
    const mutation = useRecordScopeMutation<void>(async () => {
        if (!decision) return
        await reviewPoolGrant(grant, decision, decision === "replace_with_scope_addition" ? { ...rule, module } : undefined)
    })
    return <div className="space-y-4 rounded-xl border p-4">
        <p className="text-sm font-medium">{label(grant.grantee_user_id)} · Pool shared by {label(grant.source_user_id)}</p>
        <p className="text-xs text-muted-foreground">{grant.current_record_ids.length} records in the current pool</p>
        <ChoiceField label="Pool resolution" value={decision} options={{ remove: "Remove shared pool access", replace_with_scope_addition: "Replace with individual scope addition" }} onChange={setDecision} disabled={mutation.isPending} />
        {decision === "replace_with_scope_addition" && <><ChoiceField label="Module" value={module} options={MODULE_LABELS} onChange={(value) => { setModule(value); setRule({ assignment: "assigned", phase: "all", stage_ids: [] }) }} disabled={mutation.isPending} /><ScopeFields module={module} rule={rule} onChange={setRule} addition disabled={mutation.isPending} /></>}
        {mutation.error && <PermissionError error={mutation.error} />}
        <Button size="sm" variant="outline" disabled={!decision || mutation.isPending} onClick={async () => { try { await mutation.mutateAsync(); onResolved() } catch { /* Preserve form for correction. */ } }}>{mutation.isPending ? "Saving…" : "Save pool resolution"}</Button>
    </div>
}

export function PermissionMigrationReview({ review, members, onResolved }: { review: ScopeMigrationReview; members: Member[]; onResolved: () => void }) {
    return <section className="space-y-5">
        <h3 className="font-semibold">Record access review</h3>
        {(review.missing_approval_gate_pipeline_ids ?? []).length > 0 && <div role="alert" className="rounded-xl border border-destructive/30 p-4 text-sm"><p>{review.missing_approval_gate_pipeline_ids.length} pipelines need an approval gate.</p><Link href="/settings/pipelines" className="mt-2 inline-block text-primary underline">Open pipelines</Link></div>}
        {(review.unresolved_handoffs ?? []).length > 0 && <div className="space-y-3"><p className="text-sm font-medium">{review.unresolved_handoffs.length} historical records need review</p>{review.unresolved_handoffs.map((candidate) => <HandoffReview key={`${candidate.kind}:${candidate.record_id}:${candidate.fingerprint}`} candidate={candidate} members={members} onResolved={onResolved} />)}</div>}
        {(review.legacy_pool_grants ?? []).map((grant) => <PoolGrantReview key={`${grant.id}:${grant.fingerprint}`} grant={grant} members={members} onResolved={onResolved} />)}
        {review.ready && <p className="text-sm text-emerald-700 dark:text-emerald-400">Record access review complete.</p>}
    </section>
}
