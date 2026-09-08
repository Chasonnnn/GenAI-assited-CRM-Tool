"use client"

import { useState } from "react"
import { CheckCircle2, ShieldX } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { useMembers } from "@/lib/hooks/use-permissions"
import { useCheckRecordAccess } from "@/lib/hooks/use-record-scopes"
import { ChoiceField, PermissionError, PermissionLoading } from "./permission-controls"

import { PermissionRecordPicker, type SelectedPermissionRecord } from "./permission-record-picker"
const SOURCE_LABELS: Record<string, string> = {
    role_scope: "Role scope", role: "Role scope", individual_scope: "Individual scope addition", individual_addition: "Individual addition", collaborator: "Record collaboration", intake_collaborator: "Record collaboration", legacy: "Legacy record access", protected_role: "Protected role", owner: "Assignment", assigned: "Assignment", admin: "Admin access", developer: "Developer access",
}

export function PermissionAccessChecker() {
    const members = useMembers()
    const check = useCheckRecordAccess()
    const [userId, setUserId] = useState("")
    const [record, setRecord] = useState<SelectedPermissionRecord | null>(null)
    const [personalOnly, setPersonalOnly] = useState(false)
    const resetResult = () => check.reset()
    if (members.isLoading) return <PermissionLoading />
    if (members.error) return <PermissionError error={members.error} retry={() => void members.refetch()} />
    return <section className="mx-auto max-w-3xl rounded-2xl border bg-card p-6 sm:p-8">
        <h2 className="mb-6 text-xl font-semibold">Check record access</h2>
        <div className="grid gap-5 sm:grid-cols-2">
            <ChoiceField label="Person" value={userId} options={Object.fromEntries((members.data ?? []).map((member) => [member.user_id, member.display_name || member.email]))} onChange={(value) => { setUserId(value); resetResult() }} />
        </div>
        <div className="mt-5"><PermissionRecordPicker value={record} onChange={(next) => { setRecord(next); resetResult() }} /></div>
        <label className="my-6 flex items-center justify-between gap-4 text-sm font-medium">Personal workflow scope<Switch checked={personalOnly} onCheckedChange={(value) => { setPersonalOnly(value); resetResult() }} /></label>
        <Button disabled={!userId || !record || check.isPending} onClick={() => { if (record) check.mutate({ user_id: userId, record_id: record.id, kind: record.kind, personal_only: personalOnly }) }}>{check.isPending ? "Checking…" : "Check access"}</Button>
        {check.error && <div className="mt-5"><PermissionError error={check.error} /></div>}
        {check.data && <div role="status" className="mt-6 rounded-xl border bg-muted/40 p-5">
            <div className="flex items-center gap-2 font-semibold">{check.data.allowed ? <CheckCircle2 className="size-5 text-emerald-600" /> : <ShieldX className="size-5 text-destructive" />}{check.data.allowed ? "Record visible" : "Record outside access"}</div>
            {check.data.sources.length > 0 && <ul className="mt-3 space-y-1 text-sm">{check.data.sources.map((source) => <li key={source}>{source.startsWith("individual:") ? "Individual scope addition" : SOURCE_LABELS[source] ?? "Record access rule"}</li>)}</ul>}
            {!check.data.allowed && <p className="mt-2 text-sm text-muted-foreground">{check.data.reason?.startsWith("Missing permission:") ? "The required record-view permission is missing." : check.data.reason || "No matching record scope."}</p>}
            <p className="mt-3 text-xs text-muted-foreground">Actions such as editing or sending also require the matching action permission.</p>
        </div>}
    </section>
}
