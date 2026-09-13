"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { addCollaborator, getCollaborators, getCollaboratorOptions, removeCollaborator } from "@/lib/api/record-scopes"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

export function RecordCollaborators({kind, recordId}: {kind: "surrogate" | "donor"; recordId: string}) {
    const {user} = useAuth()
    const {data: access} = useEffectivePermissions(user?.user_id ?? null)
    if ((access?.policy_version ?? 1) < 2) return null
    return <CollaboratorList kind={kind} recordId={recordId} canManage={["case_manager", "admin", "developer"].includes(access?.role ?? "")} />
}

function CollaboratorList({kind, recordId, canManage}: {kind: "surrogate" | "donor"; recordId: string; canManage: boolean}) {
    const queryClient = useQueryClient()
    const [selected, setSelected] = useState<string | null>(null)
    const queryKey = ["record-collaborators", kind, recordId]
    const collaborators = useQuery({queryKey, queryFn: () => getCollaborators(kind, recordId)})
    const options = useQuery({queryKey: [...queryKey, "options"], queryFn: () => getCollaboratorOptions(kind, recordId), enabled: canManage})
    const update = useMutation({
        mutationFn: ({userId, action}: {userId: string; action: "add" | "remove"}) => action === "add" ? addCollaborator(kind, recordId, userId) : removeCollaborator(kind, recordId, userId),
        onSuccess: () => {setSelected(null); void queryClient.invalidateQueries()},
    })
    const available = (options.data ?? []).filter(user => !collaborators.data?.some(row => row.user_id === user.user_id))
    const selection = available.find(user => user.user_id === selected)
    return <Card>
        <CardHeader><CardTitle>Intake collaborators</CardTitle></CardHeader>
        <CardContent className="space-y-4">
            {collaborators.isLoading ? <Skeleton className="h-12" /> : collaborators.isError ? <div role="alert" className="space-y-2"><p>Unable to load collaborators.</p><Button variant="outline" onClick={() => {void collaborators.refetch()}}>Retry</Button></div> : <>
                {collaborators.data?.length ? <ul className="space-y-3">{collaborators.data.map(row => <li key={row.id} className="flex items-center justify-between gap-3">
                    <span className="text-sm">{row.display_name ?? "Former member"}</span>
                    {canManage && <Button size="sm" variant="ghost" disabled={update.isPending} aria-label={`Remove ${row.display_name ?? "collaborator"}`} onClick={() => update.mutate({userId: row.user_id, action: "remove"})}>Remove</Button>}
                </li>)}</ul> : <p className="text-sm text-muted-foreground">No Intake collaborators</p>}
                {canManage && (options.isError ? <Button variant="outline" onClick={() => {void options.refetch()}}>Retry member list</Button> : <div className="flex gap-2">
                    <Select value={selected} onValueChange={setSelected} disabled={options.isLoading || update.isPending || !available.length}>
                        <SelectTrigger aria-label="Intake specialist" className="min-w-0 flex-1"><SelectValue>{() => selection?.display_name ?? (options.isLoading ? "Loading members…" : available.length ? "Select Intake specialist" : "No available members")}</SelectValue></SelectTrigger>
                        <SelectContent>{available.map(user => <SelectItem key={user.user_id} value={user.user_id}>{user.display_name}</SelectItem>)}</SelectContent>
                    </Select>
                    <Button disabled={!selection || update.isPending} onClick={() => {if (selection) update.mutate({userId: selection.user_id, action: "add"})}}>Add</Button>
                </div>)}
            </>}
            {update.isError && <p role="alert" className="text-sm text-destructive">{update.error instanceof Error ? update.error.message : "Unable to update collaborator access"}</p>}
        </CardContent>
    </Card>
}
