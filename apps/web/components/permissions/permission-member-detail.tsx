"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "@/components/app-link"
import { ChevronLeft, Lock, Plus, Trash2, UserRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useAvailablePermissions, useEffectivePermissions, useMember, useRemoveMember, useRoleDetail, useRoles, useUpdateMember } from "@/lib/hooks/use-permissions"
import { useRecordScopeMutation, useRoleScopes, useScopeAdditions, useScopeMigrationReview } from "@/lib/hooks/use-record-scopes"
import { addCollaborator, addScopeAddition, removeCollaborator, removeScopeAddition, type RecordModule, type RecordScopeRule } from "@/lib/api/record-scopes"
import { useAuth } from "@/lib/auth-context"
import { formatDate, formatRelativeTime } from "@/lib/formatters"
import { ChoiceField, MODULE_LABELS, PermissionError, PermissionLoading, ROLE_LABELS, ScopeFields, scopeLabel } from "./permission-controls"
import { PermissionRecordPicker, type SelectedPermissionRecord } from "./permission-record-picker"
import { PermissionScopeChanges } from "./permission-scope-changes"

export function PermissionMemberDetail({ memberId }: { memberId: string }) {
    const router = useRouter()
    const { user } = useAuth()
    const memberQuery = useMember(memberId)
    const member = memberQuery.data
    const actor = useEffectivePermissions(user?.user_id ?? null)
    const roles = useRoles()
    const available = useAvailablePermissions()
    const update = useUpdateMember()
    const remove = useRemoveMember()
    const v2 = member?.policy_version === 2
    const manageable = !!member?.capabilities?.can_manage_members
    const roleDetail = useRoleDetail(member?.role ?? null)
    const additionsEnabled = !!member && v2 && !!actor.data?.capabilities?.can_manage_roles
    const additions = useScopeAdditions(member?.user_id ?? "", additionsEnabled)
    const scopeReview = useScopeMigrationReview(additionsEnabled)
    const collaborators = (scopeReview.data?.collaborators ?? []).filter((item) => item.user_id === member?.user_id)
    const [role, setRole] = useState("")
    const [reviewOpen, setReviewOpen] = useState(false)
    const currentRoleScopes = useRoleScopes(member?.role ?? "", v2 && reviewOpen)
    const proposedRoleScopes = useRoleScopes(role, v2 && reviewOpen)
    const [retainAdditions, setRetainAdditions] = useState<"keep" | "remove" | "">("")
    const [retainCollaborators, setRetainCollaborators] = useState<"keep" | "remove" | "">("")
    const proposedRole = useRoleDetail(role || null)
    const [addActionOpen, setAddActionOpen] = useState(false)
    const [permission, setPermission] = useState("")
    const [overrideType, setOverrideType] = useState<"grant" | "revoke">("grant")
    const [scopeOpen, setScopeOpen] = useState(false)
    const [scopeModule, setScopeModule] = useState<RecordModule>("surrogates")
    const [scopeRule, setScopeRule] = useState<RecordScopeRule>({ assignment: "assigned", phase: "all", stage_ids: [] })
    const [collaboratorOpen, setCollaboratorOpen] = useState(false)
    const [record, setRecord] = useState<SelectedPermissionRecord | null>(null)
    const [removeOpen, setRemoveOpen] = useState(false)
    const scopeMutation = useRecordScopeMutation<void>(async () => { if (member) await addScopeAddition(member.user_id, { ...scopeRule, module: scopeModule }) })
    const scopeRemoval = useRecordScopeMutation<string>((id) => removeScopeAddition(member!.user_id, id))
    const collaborationMutation = useRecordScopeMutation<void>(async () => { if (member && record && record.kind !== "intended_parent") await addCollaborator(record.kind, record.id, member.user_id) })
    const collaborationRemoval = useRecordScopeMutation<{ kind: "surrogate" | "donor"; id: string }>((item) => removeCollaborator(item.kind, item.id, member!.user_id))
    const label = (key: string) => available.data?.find((item) => item.key === key)?.label || key.replaceAll("_", " ")
    const allRolePermissions = Object.values(roleDetail.data?.permissions_by_category ?? {}).flat().filter((item) => item.is_granted)
    const inherited = v2 ? (member?.effective_permissions ?? []).filter((key) => key !== "view_post_approval_surrogates" && member?.access_sources?.[key]?.some((source) => source === "role_baseline" || source === "developer")) : allRolePermissions.map((item) => item.key)
    const canAdd = manageable && !!member?.capabilities?.can_add_permissions && !!roleDetail.data && !roleDetail.data.protected && member?.is_active !== false
    const permissionOptions = (available.data ?? []).filter((item) => !(v2 && item.key === "view_post_approval_surrogates") && item.assignable !== false && !item.developer_only && !(member?.overrides ?? []).some((override) => override.permission === item.key) && (overrideType === "grant" ? !member?.effective_permissions.includes(item.key) : member?.effective_permissions.includes(item.key)))
    const nextActions = new Set(Object.values(proposedRole.data?.permissions_by_category ?? {}).flat().filter((item) => item.is_granted).map((item) => item.key))
    if (!proposedRole.data?.protected && (!v2 || retainAdditions === "keep")) member?.overrides.filter((item) => item.override_type === "grant" && available.data?.some((permission) => permission.key === item.permission)).forEach((item) => nextActions.add(item.permission))
    if (!v2) member?.overrides.filter((item) => item.override_type === "revoke").forEach((item) => nextActions.delete(item.permission))
    const gained = [...nextActions].filter((key) => !member?.effective_permissions.includes(key))
    const lost = member?.effective_permissions.filter((key) => !nextActions.has(key)) ?? []
    const scopeLoading = additions.isLoading || scopeReview.isLoading || currentRoleScopes.isLoading || proposedRoleScopes.isLoading
    const scopeError = additions.error || scopeReview.error || currentRoleScopes.error || proposedRoleScopes.error
    const accessReviewReady = !v2 || (!!retainAdditions && !!retainCollaborators && !scopeLoading && !scopeError)
    const changeRole = async () => {
        if (!member || !role) return
        try {
            await update.mutateAsync({ memberId, data: { role, ...(v2 ? { access_reviewed: true, retain_additions: retainAdditions === "keep", retain_collaborators: retainCollaborators === "keep" } : {}) } })
            setRole(""); setReviewOpen(false); setRetainAdditions(""); setRetainCollaborators("")
        } catch { /* Keep the review available for correction. */ }
    }
    if (memberQuery.isLoading) return <PermissionLoading />
    if (memberQuery.error) return <PermissionError error={memberQuery.error} retry={() => void memberQuery.refetch()} />
    if (!member) return <p className="p-8 text-muted-foreground">Member not found.</p>
    return <div className="mx-auto w-full max-w-5xl space-y-6 p-6 sm:p-8">
        <Button variant="ghost" size="sm" render={<Link href="/settings/team" />}><ChevronLeft className="size-4" />People</Button>
        <section className="rounded-2xl border bg-card p-6 sm:p-8">
            <div className="flex items-center gap-4"><div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"><UserRound className="size-7" /></div><div><h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold">{member.display_name || member.email}{member.user_id === user?.user_id && <Badge variant="outline">You</Badge>}{member.is_active === false && <Badge variant="secondary">Inactive</Badge>}</h1><p className="mt-1 text-sm text-muted-foreground">{member.email}</p></div></div>
            <div className="my-6 flex gap-8 text-sm"><div><span className="text-muted-foreground">Joined</span><p>{formatDate(member.created_at, { dateStyle: "medium" }, "—")}</p></div><div><span className="text-muted-foreground">Last login</span><p>{member.last_login_at ? formatRelativeTime(member.last_login_at, "—") : "Never"}</p></div></div>
            {member.is_active === false && <p className="mb-5 rounded-xl bg-muted p-4 text-sm">This member has no active access. Review their role before accepting a returning invitation.</p>}
            {roles.error ? <PermissionError error={roles.error} /> : <div className="flex items-end gap-3"><div className="flex-1"><ChoiceField label="Role" value={role || member.role} options={Object.fromEntries((roles.data ?? []).filter((item) => item.role !== "developer" || actor.data?.capabilities?.can_assign_developer || member.role === "developer").map((item) => [item.role, ROLE_LABELS[item.role] || item.label]))} onChange={(value) => { setRole(value === member.role ? "" : value); setRetainAdditions(""); setRetainCollaborators(""); update.reset() }} disabled={!manageable || roles.isLoading || update.isPending} /></div>{role && <Button disabled={update.isPending} onClick={() => setReviewOpen(true)}>Review role change</Button>}</div>}
        </section>
        <div className="grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border bg-card p-6"><h2 className="mb-5 flex items-center gap-2 font-semibold"><Lock className="size-4 text-muted-foreground" />Role permissions</h2>{roleDetail.isLoading ? <PermissionLoading /> : roleDetail.error ? <PermissionError error={roleDetail.error} /> : inherited.length ? <ul className="grid gap-3 text-sm">{inherited.map((key) => <li key={key}>{label(key)}</li>)}</ul> : <p className="text-sm text-muted-foreground">No inherited action permissions.</p>}</section>
            <section className="rounded-2xl border bg-card p-6"><div className="mb-5 flex items-center justify-between gap-3"><h2 className="font-semibold">{v2 ? "Individual additions" : "Permission overrides"}</h2>{canAdd && <Button size="sm" variant="outline" onClick={() => { setPermission(""); setOverrideType("grant"); update.reset(); setAddActionOpen(true) }}><Plus className="size-4" />{v2 ? "Add permission" : "Add override"}</Button>}</div>
                {member.overrides.length ? <ul className="space-y-3">{member.overrides.map((item) => <li key={item.permission} className="flex items-center justify-between gap-3 rounded-xl bg-muted/50 p-3 text-sm"><span>{item.label}{item.override_type === "revoke" && <Badge variant="outline" className="ml-2">Revoked</Badge>}</span>{manageable && !roleDetail.data?.protected && <Button aria-label={`Remove ${item.label} ${v2 ? "addition" : "override"}`} variant="ghost" size="icon-sm" disabled={update.isPending} onClick={async () => { try { await update.mutateAsync({ memberId, data: { remove_overrides: [item.permission] } }) } catch { /* Render mutation error below. */ } }}><Trash2 className="size-4" /></Button>}</li>)}</ul> : <p className="text-sm text-muted-foreground">{v2 ? "No individual action additions." : "No permission overrides."}</p>}
                {update.error && !reviewOpen && !addActionOpen && <div className="mt-4"><PermissionError error={update.error} /></div>}
            </section>
        </div>
        {v2 && additionsEnabled && <div className="grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border bg-card p-6"><div className="mb-5 flex items-center justify-between gap-3"><h2 className="font-semibold">Record scope additions</h2>{canAdd && <Button variant="outline" size="sm" onClick={() => { scopeMutation.reset(); setScopeOpen(true) }}><Plus className="size-4" />Add scope</Button>}</div>{additions.isLoading ? <PermissionLoading /> : additions.error ? <PermissionError error={additions.error} retry={() => void additions.refetch()} /> : additions.data?.length ? <ul className="space-y-3">{additions.data.map((item) => <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl bg-muted/50 p-3 text-sm"><span className="font-medium">{MODULE_LABELS[item.module]}<span className="mt-1 block text-xs font-normal text-muted-foreground">{scopeLabel(item)}</span></span>{manageable && <Button variant="ghost" size="icon-sm" aria-label={`Remove ${MODULE_LABELS[item.module]} scope addition`} disabled={scopeRemoval.isPending} onClick={() => scopeRemoval.mutate(item.id)}><Trash2 className="size-4" /></Button>}</li>)}</ul> : <p className="text-sm text-muted-foreground">No additional record scope.</p>}{scopeRemoval.error && <PermissionError error={scopeRemoval.error} />}</section>
            <section className="rounded-2xl border bg-card p-6"><div className="mb-5 flex items-center justify-between gap-3"><h2 className="font-semibold">Record collaborations</h2>{canAdd && member.capabilities?.can_receive_collaboration && <Button variant="outline" size="sm" onClick={() => { collaborationMutation.reset(); setRecord(null); setCollaboratorOpen(true) }}><Plus className="size-4" />Add record</Button>}</div>{scopeReview.isLoading ? <PermissionLoading /> : scopeReview.error ? <PermissionError error={scopeReview.error} retry={() => void scopeReview.refetch()} /> : collaborators.length ? <ul className="space-y-3">{collaborators.map((item) => { const kind = item.surrogate_id ? "surrogate" : "donor"; const id = item.surrogate_id || item.donor_id!; return <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl bg-muted/50 p-3 text-sm"><Link href={`/${kind === "surrogate" ? "surrogates" : "donors"}/${id}`} className="text-primary underline underline-offset-4">{item.record_number || `Open ${kind} record`}</Link>{manageable && <Button variant="ghost" size="icon-sm" aria-label={`Remove ${kind} collaboration`} disabled={collaborationRemoval.isPending} onClick={() => collaborationRemoval.mutate({ kind, id })}><Trash2 className="size-4" /></Button>}</li> })}</ul> : <p className="text-sm text-muted-foreground">No record collaborations.</p>}{collaborationRemoval.error && <PermissionError error={collaborationRemoval.error} />}</section>
        </div>}
        {manageable && member.is_active !== false && <div className="flex items-center justify-between gap-4 rounded-2xl border border-destructive/25 p-6"><h2 className="font-medium">Remove from organization</h2><Button variant="destructive" onClick={() => setRemoveOpen(true)}>Remove member</Button></div>}
        <Dialog open={reviewOpen} onOpenChange={(open) => { if (!update.isPending) setReviewOpen(open) }}><DialogContent className="sm:max-w-xl"><DialogHeader><DialogTitle>Review role change</DialogTitle><DialogDescription>{ROLE_LABELS[member.role]} → {ROLE_LABELS[role]}</DialogDescription></DialogHeader>
            {proposedRole.isLoading || (v2 && scopeLoading) ? <PermissionLoading /> : proposedRole.error || scopeError ? <PermissionError error={proposedRole.error || scopeError} /> : <div className="max-h-[55vh] space-y-5 overflow-y-auto">
                {v2 && <><ChoiceField label={`Action and scope additions (${member.overrides.filter((item) => item.override_type === "grant").length + (additions.data?.length ?? 0)})`} value={retainAdditions} options={{ keep: "Keep existing additions", remove: "Remove existing additions" }} onChange={setRetainAdditions} disabled={update.isPending} /><ChoiceField label={`Record collaborations (${collaborators.length})`} value={retainCollaborators} options={{ keep: "Keep existing collaborations", remove: "Remove existing collaborations" }} onChange={setRetainCollaborators} disabled={update.isPending} /></>}
                <div className="grid gap-4 text-sm sm:grid-cols-2"><div><h3 className="mb-2 font-medium">Added actions</h3><ul className="space-y-1">{gained.length ? gained.map((key) => <li key={key}>{label(key)}</li>) : <li className="text-muted-foreground">None</li>}</ul></div><div><h3 className="mb-2 font-medium">Removed actions</h3><ul className="space-y-1">{lost.length ? lost.map((key) => <li key={key}>{label(key)}</li>) : <li className="text-muted-foreground">None</li>}</ul></div></div>
                {v2 && currentRoleScopes.data && proposedRoleScopes.data && <PermissionScopeChanges before={currentRoleScopes.data} after={proposedRoleScopes.data} />}
                {(additions.data?.length ?? 0) > 0 && <ul className="space-y-2 text-sm">{additions.data?.map((item) => <li key={item.id}>{MODULE_LABELS[item.module]} · {scopeLabel(item)}</li>)}</ul>}
            </div>}{update.error && <PermissionError error={update.error} />}<DialogFooter><Button variant="outline" disabled={update.isPending} onClick={() => setReviewOpen(false)}>Back</Button><Button disabled={!accessReviewReady || proposedRole.isLoading || !!proposedRole.error || update.isPending} onClick={() => void changeRole()}>{update.isPending ? "Applying…" : "Apply role change"}</Button></DialogFooter>
        </DialogContent></Dialog>
        <Dialog open={addActionOpen} onOpenChange={(open) => { if (!update.isPending) setAddActionOpen(open) }}><DialogContent><DialogHeader><DialogTitle>{v2 ? "Add individual permission" : "Add permission override"}</DialogTitle></DialogHeader>{available.isLoading ? <PermissionLoading /> : available.error ? <PermissionError error={available.error} /> : <>{!v2 && <ChoiceField label="Override type" value={overrideType} options={{ grant: "Grant permission", revoke: "Revoke permission" }} onChange={(value) => { setOverrideType(value); setPermission("") }} />}<ChoiceField label="Permission" value={permission} options={Object.fromEntries(permissionOptions.map((item) => [item.key, item.label]))} onChange={setPermission} />{permissionOptions.length === 0 && <p className="text-sm text-muted-foreground">No additional permissions available.</p>}</>}{update.error && <PermissionError error={update.error} />}<DialogFooter><Button variant="outline" disabled={update.isPending} onClick={() => setAddActionOpen(false)}>Cancel</Button><Button disabled={!permission || update.isPending} onClick={async () => { try { await update.mutateAsync({ memberId, data: { add_overrides: [{ permission, override_type: v2 ? "grant" : overrideType }] } }); setAddActionOpen(false) } catch { /* Keep the rejected addition visible. */ } }}>{update.isPending ? "Saving…" : v2 ? "Add permission" : "Add override"}</Button></DialogFooter></DialogContent></Dialog>
        <Dialog open={scopeOpen} onOpenChange={(open) => { if (!scopeMutation.isPending) setScopeOpen(open) }}><DialogContent><DialogHeader><DialogTitle>Add record scope</DialogTitle></DialogHeader><ChoiceField label="Module" value={scopeModule} options={MODULE_LABELS} onChange={(value) => { setScopeModule(value); setScopeRule({ assignment: "assigned", phase: "all", stage_ids: [] }) }} /><ScopeFields module={scopeModule} rule={scopeRule} onChange={setScopeRule} addition disabled={scopeMutation.isPending} />{scopeMutation.error && <PermissionError error={scopeMutation.error} />}<DialogFooter><Button variant="outline" disabled={scopeMutation.isPending} onClick={() => setScopeOpen(false)}>Cancel</Button><Button disabled={scopeMutation.isPending} onClick={async () => { try { await scopeMutation.mutateAsync(); setScopeOpen(false) } catch { /* Keep the rejected addition visible. */ } }}>{scopeMutation.isPending ? "Saving…" : "Add scope"}</Button></DialogFooter></DialogContent></Dialog>
        <Dialog open={collaboratorOpen} onOpenChange={(open) => { if (!collaborationMutation.isPending) setCollaboratorOpen(open) }}><DialogContent><DialogHeader><DialogTitle>Add record collaboration</DialogTitle></DialogHeader><PermissionRecordPicker value={record} onChange={setRecord} collaboratorsOnly disabled={collaborationMutation.isPending} />{collaborationMutation.error && <PermissionError error={collaborationMutation.error} />}<DialogFooter><Button variant="outline" disabled={collaborationMutation.isPending} onClick={() => setCollaboratorOpen(false)}>Cancel</Button><Button disabled={!record || collaborationMutation.isPending} onClick={async () => { try { await collaborationMutation.mutateAsync(); setCollaboratorOpen(false) } catch { /* Keep the rejected addition visible. */ } }}>{collaborationMutation.isPending ? "Saving…" : "Add collaboration"}</Button></DialogFooter></DialogContent></Dialog>
        <Dialog open={removeOpen} onOpenChange={(open) => { if (!remove.isPending) setRemoveOpen(open) }}><DialogContent><DialogHeader><DialogTitle>Remove {member.display_name || member.email}?</DialogTitle><DialogDescription>Organization access ends immediately.</DialogDescription></DialogHeader>{remove.error && <PermissionError error={remove.error} />}<DialogFooter><Button variant="outline" disabled={remove.isPending} onClick={() => setRemoveOpen(false)}>Cancel</Button><Button variant="destructive" disabled={remove.isPending} onClick={async () => { try { await remove.mutateAsync(memberId); router.push("/settings/team") } catch { /* Render the mutation error. */ } }}>{remove.isPending ? "Removing…" : "Remove member"}</Button></DialogFooter></DialogContent></Dialog>
    </div>
}
