"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "@/components/ui/toast"
import { useDonorOwnerOptions, useUpdateDonor, useClaimDonor } from "@/lib/hooks/use-donors"
import type { Donor } from "@/lib/types/donor"

export function DonorOwnershipSection({ donor, canEdit, canClaim = false }: { donor: Donor; canEdit: boolean; canClaim?: boolean }) {
    const [open, setOpen] = useState(false)
    const [selection, setSelection] = useState("none")
    const optionsQuery = useDonorOwnerOptions(canEdit)
    const updateDonor = useUpdateDonor()
    const claimDonor = useClaimDonor()
    const isPool = donor.owner_type === "queue" && (donor.owner_name === "Donor Pool" || optionsQuery.data?.queues.some(queue => queue.id === donor.owner_id && queue.name === "Donor Pool"))
    const options = [
        { value: "none", label: "Unassigned" },
        ...(optionsQuery.data?.users ?? []).map((user) => ({ value: `user:${user.id}`, label: user.display_name })),
        ...(optionsQuery.data?.queues ?? []).map((queue) => ({ value: `queue:${queue.id}`, label: queue.name })),
    ]
    const currentValue = donor.owner_type && donor.owner_id ? `${donor.owner_type}:${donor.owner_id}` : "none"
    const ownerLabel = donor.owner_name ?? options.find((option) => option.value === currentValue)?.label
        ?? (donor.owner_type === "queue" ? "Assigned queue" : "Assigned user")
    const selectedLabel = options.find((option) => option.value === selection)?.label ?? ownerLabel
    const selectionAvailable = options.some((option) => option.value === selection)

    const handleSave = async () => {
        const separator = selection.indexOf(":")
        const ownerType = selection.slice(0, separator)
        if (selection !== "none" && ownerType !== "user" && ownerType !== "queue") return
        try {
            await updateDonor.mutateAsync({ id: donor.id, data: selection === "none"
                ? { owner_type: null, owner_id: null }
                : { owner_type: ownerType as "user" | "queue", owner_id: selection.slice(separator + 1) } })
            setOpen(false)
            toast.success("Owner updated")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to update owner")
        }
    }

    const handleClaim = async () => {
        try {
            await claimDonor.mutateAsync(donor.id)
            toast.success("Donor assigned to you")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to claim donor")
        }
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle><h2>Owner</h2></CardTitle>
                <div className="flex gap-2">
                {canClaim && isPool && !donor.is_archived ? <Button size="sm" disabled={claimDonor.isPending} onClick={() => { void handleClaim() }}>{claimDonor.isPending ? "Claiming…" : "Assign to me"}</Button> : null}
                {canEdit && !donor.is_archived ? <Button size="sm" variant="outline" onClick={() => { setSelection(currentValue); setOpen(true) }}>Change Owner</Button> : null}
                </div>
            </CardHeader>
            <CardContent><p className="text-sm">{ownerLabel}</p></CardContent>
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent>
                    <DialogHeader><DialogTitle>Change Owner</DialogTitle></DialogHeader>
                    {optionsQuery.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading owners…</p>
                        : optionsQuery.isError ? <div className="space-y-3"><p className="text-sm text-destructive">Failed to load owners.</p><Button variant="outline" onClick={() => { void optionsQuery.refetch() }}>Retry owners</Button></div>
                        : <div className="space-y-2">
                            <Label htmlFor="donor-owner">Owner</Label>
                            <Select value={selection} onValueChange={(value) => { if (value) setSelection(value) }}>
                                <SelectTrigger id="donor-owner"><SelectValue>{() => selectedLabel}</SelectValue></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">Unassigned</SelectItem>
                                    {!selectionAvailable ? <SelectItem value={selection} disabled>{ownerLabel}</SelectItem> : null}
                                    <SelectGroup aria-label="Members">{optionsQuery.data?.users.map((user) => <SelectItem key={user.id} value={`user:${user.id}`}>{user.display_name}</SelectItem>)}</SelectGroup>
                                    <SelectGroup aria-label="Queues">{optionsQuery.data?.queues.map((queue) => <SelectItem key={queue.id} value={`queue:${queue.id}`}>{queue.name}</SelectItem>)}</SelectGroup>
                                </SelectContent>
                            </Select>
                        </div>}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                        <Button onClick={() => { void handleSave() }} disabled={optionsQuery.isLoading || optionsQuery.isError || !selectionAvailable || selection === currentValue || updateDonor.isPending}>{updateDonor.isPending ? "Saving…" : "Save Owner"}</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    )
}
