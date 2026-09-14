"use client"

import { useState } from "react"
import { CheckIcon, Loader2Icon, UserIcon } from "lucide-react"
import { DropdownMenuItem, DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from "@/components/ui/dropdown-menu"
import { useDonorOwnerOptions, useUpdateDonor } from "@/lib/hooks/use-donors"
import { toast } from "@/components/ui/toast"
import type { Donor, DonorOwnerType } from "@/lib/types/donor"

export function DonorAssignMenu({ donor }: { donor: Donor }) {
    const [open, setOpen] = useState(false)
    const query = useDonorOwnerOptions(open)
    const update = useUpdateDonor()
    const assign = async (owner_type: DonorOwnerType | null, owner_id: string | null) => {
        try {
            await update.mutateAsync({ id: donor.id, data: { owner_type, owner_id } })
            toast.success(owner_id ? "Donor assigned" : "Donor unassigned")
        } catch { toast.error("Unable to update assignment") }
    }
    const options = [
        ...(query.data?.users ?? []).map(user => ({ type: "user" as const, id: user.id, label: user.display_name })),
        ...(query.data?.queues ?? []).map(queue => ({ type: "queue" as const, id: queue.id, label: queue.name })),
    ]
    return <DropdownMenuSub open={open} onOpenChange={setOpen}>
        <DropdownMenuSubTrigger><UserIcon className="size-4" />Assign</DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="max-h-80 overflow-y-auto">
            {query.isLoading ? <DropdownMenuItem disabled><Loader2Icon className="size-4 animate-spin" />Loading…</DropdownMenuItem>
                : query.isError ? <DropdownMenuItem onClick={event => { event.preventDefault(); void query.refetch() }}>Retry owners</DropdownMenuItem>
                    : <>
                        {options.map(option => {
                            const selected = donor.owner_type === option.type && donor.owner_id === option.id
                            return <DropdownMenuItem key={`${option.type}:${option.id}`} disabled={selected || update.isPending} onClick={() => { void assign(option.type, option.id) }}>
                                {option.label}{selected && <CheckIcon className="ml-auto size-4" />}
                            </DropdownMenuItem>
                        })}
                        {options.length === 0 && <DropdownMenuItem disabled>No assignees available</DropdownMenuItem>}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem disabled={!donor.owner_id || update.isPending} onClick={() => { void assign(null, null) }}>Unassign</DropdownMenuItem>
                    </>}
        </DropdownMenuSubContent>
    </DropdownMenuSub>
}
