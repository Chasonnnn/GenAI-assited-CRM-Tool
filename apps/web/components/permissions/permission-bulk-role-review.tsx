"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { getMember } from "@/lib/api/permissions"
import { getRoleScopes, getScopeAdditions } from "@/lib/api/record-scopes"
import { useBulkUpdateRoles, useRoleDetail, useRoles } from "@/lib/hooks/use-permissions"
import { useRoleScopes, useScopeMigrationReview } from "@/lib/hooks/use-record-scopes"
import { ChoiceField, MODULE_LABELS, PermissionError, PermissionLoading, ROLE_LABELS, scopeLabel } from "./permission-controls"
import { PermissionScopeChanges } from "./permission-scope-changes"

export function PermissionBulkRoleReview({ memberIds, v2, canAssignDeveloper, onClose, onSaved }: { memberIds: string[]; v2: boolean; canAssignDeveloper: boolean; onClose: () => void; onSaved: () => void }) {
    const [role, setRole] = useState("case_manager")
    const [retainAdditions, setRetainAdditions] = useState<"keep" | "remove" | "">("")
    const [retainCollaborators, setRetainCollaborators] = useState<"keep" | "remove" | "">("")
    const [partialFailure, setPartialFailure] = useState<string | null>(null)
    const roles = useRoles()
    const proposedRole = useRoleDetail(role)
    const proposedScopes = useRoleScopes(role, v2)
    const members = useQuery({ queryKey: ["permissions", "members", "bulk-review", [...memberIds].sort()], queryFn: async () => {
        const roleScopes = new Map<string, ReturnType<typeof getRoleScopes>>()
        return Promise.all(memberIds.map(async (id) => {
            const member = await getMember(id)
            if (v2 && !roleScopes.has(member.role)) roleScopes.set(member.role, getRoleScopes(member.role))
            return { member, scopes: v2 ? await getScopeAdditions(member.user_id) : [], roleScopes: v2 ? await roleScopes.get(member.role) : undefined }
        }))
    } })
    const collaborations = useScopeMigrationReview(v2)
    const mutation = useBulkUpdateRoles()
    const loading = members.isLoading || roles.isLoading || proposedRole.isLoading || (v2 && (collaborations.isLoading || proposedScopes.isLoading))
    const error = members.error || roles.error || proposedRole.error || (v2 && (collaborations.error || proposedScopes.error))
    const baseline = Object.values(proposedRole.data?.permissions_by_category ?? {}).flat().filter((item) => item.is_granted)
    return <DialogContent className="sm:max-w-xl"><DialogHeader><DialogTitle>Review role changes</DialogTitle><DialogDescription>{memberIds.length} selected members</DialogDescription></DialogHeader>
        {loading ? <PermissionLoading /> : error ? <PermissionError error={error} retry={() => { void members.refetch(); void roles.refetch(); void proposedRole.refetch(); if (v2) void collaborations.refetch() }} /> : <div className="max-h-[60vh] space-y-5 overflow-y-auto">
            <ChoiceField label="New role" value={role} options={Object.fromEntries((roles.data ?? []).filter((item) => item.role !== "developer" || canAssignDeveloper).map((item) => [item.role, ROLE_LABELS[item.role] || item.label]))} onChange={setRole} disabled={mutation.isPending} />
            {v2 && <><ChoiceField label="Action and scope additions" value={retainAdditions} options={{ keep: "Keep each member’s existing additions", remove: "Remove each member’s existing additions" }} onChange={setRetainAdditions} disabled={mutation.isPending} /><ChoiceField label="Record collaborations" value={retainCollaborators} options={{ keep: "Keep each member’s collaborations", remove: "Remove each member’s collaborations" }} onChange={setRetainCollaborators} disabled={mutation.isPending} /></>}
            {(members.data ?? []).map(({ member, scopes, roleScopes }) => {
                const actionAdditions = member.overrides.filter((item) => item.override_type === "grant")
                const recordCount = collaborations.data?.collaborators.filter((item) => item.user_id === member.user_id).length ?? 0
                const next = new Set(baseline.map((item) => item.key))
                if (!proposedRole.data?.protected && (!v2 || retainAdditions === "keep")) actionAdditions.forEach((item) => next.add(item.permission))
                if (!v2) member.overrides.filter((item) => item.override_type === "revoke").forEach((item) => next.delete(item.permission))
                const lost = member.effective_permissions.filter((key) => !next.has(key))
                const gained = baseline.filter((item) => !member.effective_permissions.includes(item.key))
                return <details key={member.id} className="rounded-xl border p-4"><summary className="cursor-pointer text-sm font-medium">{member.display_name || member.email} · {ROLE_LABELS[member.role]}{member.is_active === false ? " · Inactive" : ""}</summary><div className="mt-4 space-y-3 text-sm"><p>{actionAdditions.length} action additions · {scopes.length} scope additions · {recordCount} collaborations</p>{actionAdditions.length > 0 && <ul>{actionAdditions.map((item) => <li key={item.permission}>{item.label}</li>)}</ul>}{scopes.length > 0 && <ul>{scopes.map((item) => <li key={item.id}>{MODULE_LABELS[item.module]} · {scopeLabel(item)}</li>)}</ul>}{v2 && roleScopes && proposedScopes.data && <PermissionScopeChanges before={roleScopes} after={proposedScopes.data} />}<p>Added actions: {gained.map((item) => item.label).join(", ") || "None"}</p><p>Removed actions: {lost.map((key) => member.overrides.find((item) => item.permission === key)?.label || Object.values(proposedRole.data?.permissions_by_category ?? {}).flat().find((item) => item.key === key)?.label || key.replaceAll("_", " ")).join(", ") || "None"}</p></div></details>
            })}
        </div>}
        {partialFailure && <p role="alert" className="text-sm text-destructive">{partialFailure}</p>}{mutation.error && <PermissionError error={mutation.error} />}
        <DialogFooter><Button variant="outline" disabled={mutation.isPending} onClick={onClose}>Cancel</Button><Button disabled={loading || !!error || mutation.isPending || (v2 && (!retainAdditions || !retainCollaborators))} onClick={async () => { try { const result = await mutation.mutateAsync({ memberIds, role, ...(v2 ? { review: { access_reviewed: true, retain_additions: retainAdditions === "keep", retain_collaborators: retainCollaborators === "keep" } } : {}) }); if (result.failed) setPartialFailure(`${result.success} updated; ${result.failed} failed. Review current access before retrying.`); else onSaved() } catch { /* Keep selected members available for correction. */ } }}>{mutation.isPending ? "Applying…" : "Apply reviewed roles"}</Button></DialogFooter>
    </DialogContent>
}
