"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { addCollaborator, getCollaborators, getCollaboratorOptions, removeCollaborator } from "@/lib/api/record-scopes"
import { useRecordScopeMutation } from "@/lib/hooks/use-record-scopes"
import { ChoiceField, PermissionError, PermissionLoading } from "./permission-controls"

export function RecordCollaboratorsDialog({ kind, recordId, open, onOpenChange, canManage }: {
    kind: "surrogate" | "donor"
    recordId: string
    open: boolean
    onOpenChange: (open: boolean) => void
    canManage: boolean
}) {
    const [userId, setUserId] = useState("")
    const enabled = open && canManage
    const collaborators = useQuery({ queryKey: ["record-scopes", kind, recordId, "collaborators"], queryFn: () => getCollaborators(kind, recordId), enabled })
    const options = useQuery({ queryKey: ["record-scopes", kind, recordId, "collaborator-options"], queryFn: () => getCollaboratorOptions(kind, recordId), enabled })
    const add = useRecordScopeMutation<string>((id) => addCollaborator(kind, recordId, id))
    const remove = useRecordScopeMutation<string>((id) => removeCollaborator(kind, recordId, id))
    const pending = add.isPending || remove.isPending
    const available = (options.data ?? []).filter((option) => !collaborators.data?.some((item) => item.user_id === option.user_id))
    const selected = available.some((option) => option.user_id === userId) ? userId : ""
    return <Dialog open={open && canManage} onOpenChange={(next) => { if (!pending) onOpenChange(next) }}>
        <DialogContent>
            <DialogHeader><DialogTitle>Collaborators</DialogTitle></DialogHeader>
            {collaborators.isLoading ? <PermissionLoading /> : collaborators.error ? <PermissionError error={collaborators.error} retry={() => void collaborators.refetch()} /> : <>
                {collaborators.data?.length ? <ul className="space-y-2">{collaborators.data.map((item) => <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl border p-3 text-sm">
                    <span>{item.display_name || "Team member"}</span>
                    <Button variant="ghost" size="icon-sm" aria-label={`Remove ${item.display_name || "team member"}`} disabled={pending} onClick={() => { add.reset(); remove.mutate(item.user_id) }}><Trash2 className="size-4" /></Button>
                </li>)}</ul> : <p className="py-3 text-sm text-muted-foreground">No collaborators.</p>}
                {options.isLoading ? <PermissionLoading /> : options.error ? <PermissionError error={options.error} retry={() => void options.refetch()} /> : <div className="flex items-end gap-3 border-t pt-4">
                    <div className="min-w-0 flex-1"><ChoiceField label="Team member" value={selected} options={Object.fromEntries(available.map((option) => [option.user_id, option.display_name]))} disabled={pending || !available.length} onChange={(value) => { setUserId(value); add.reset(); remove.reset() }} /></div>
                    <Button disabled={!selected || pending} onClick={async () => { try { await add.mutateAsync(selected); setUserId("") } catch { /* Mutation error remains visible. */ } }}>{add.isPending ? "Adding…" : "Add"}</Button>
                </div>}
            </>}
            {(add.error || remove.error) && <PermissionError error={add.error || remove.error} />}
        </DialogContent>
    </Dialog>
}
