"use client"

import type { Route } from "next"
import { useRouter } from "next/navigation"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircleIcon, ChevronsUpDownIcon, Loader2Icon } from "lucide-react"
import { showMatchProposedToast } from "@/components/matches/match-proposed-toast"
import { useAuth } from "@/lib/auth-context"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { cn } from "@/lib/utils"

type IntendedParentOption = {
    id: string
    full_name?: string | null
    email?: string | null
    intended_parent_number?: string | null
}

function getIntendedParentLabel(ip: IntendedParentOption): string {
    return ip.full_name || ip.email || "Unknown intended parent"
}

function matchesIntendedParentQuery(ip: IntendedParentOption, query: string): boolean {
    const needle = query.trim().toLowerCase()
    if (!needle) return true
    return [ip.full_name, ip.email, ip.intended_parent_number]
        .some((value) => value?.toLowerCase().includes(needle))
}

interface ProposeMatchDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateId?: string
    donorId?: string
    donorName?: string
    surrogateName?: string
    onSuccess?: () => void
}

export function ProposeMatchDialog({
    open,
    onOpenChange,
    surrogateId,
    surrogateName,
    donorId,
    donorName,
    onSuccess,
}: ProposeMatchDialogProps) {
    const [selectedIpId, setSelectedIpId] = useState<string>("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)
    const [isIpPickerOpen, setIsIpPickerOpen] = useState(false)
    const [ipQuery, setIpQuery] = useState("")
    const ipTriggerRef = useRef<HTMLButtonElement | null>(null)

    const router = useRouter()
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const permissions = permissionsQuery.data?.permissions ?? []
    const permissionsLoaded = !permissionsQuery.isLoading
    const canViewIntendedParents = permissions.includes("view_intended_parents")
    const canLoadIntendedParents = open && canViewIntendedParents

    const { data: ipsData, isLoading: ipsLoading } = useIntendedParents(
        { per_page: 100 },
        { enabled: canLoadIntendedParents }
    )
    const createMatch = useCreateMatch()
    const intendedParents: IntendedParentOption[] = ipsData?.items ?? []
    const selectedIp = intendedParents.find((ip) => ip.id === selectedIpId) ?? null
    const filteredIntendedParents = intendedParents.filter((ip) => matchesIntendedParentQuery(ip, ipQuery))

    const handleIpPickerOpenChange = (nextOpen: boolean) => {
        setIsIpPickerOpen(nextOpen)
        if (!nextOpen) setIpQuery("")
    }

    const handleSubmit = async () => {
        if (!selectedIpId || (!surrogateId && !donorId)) return
        setError(null)

        try {
            const match = await createMatch.mutateAsync({
                ...(donorId ? { donor_id: donorId, match_kind: "donor" as const } : { surrogate_id: surrogateId! }),
                intended_parent_id: selectedIpId,
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            showMatchProposedToast(match, (href) => router.push(href as Route))
            onOpenChange(false)
            setSelectedIpId("")
            setNotes("")
            onSuccess?.()
        } catch (e: unknown) {
            setError(getActionErrorMessage(e, "Couldn't propose match. Try again."))
        }
    }

    const handleClose = () => {
        onOpenChange(false)
        setSelectedIpId("")
        setNotes("")
        setError(null)
        handleIpPickerOpenChange(false)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent size="md" initialFocus={ipTriggerRef}>
                <DialogHeader>
                    <DialogTitle>
                        {(donorName || surrogateName) ? `Propose match for ${donorName || surrogateName}` : "Propose Match"}
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {error && (
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                    <div className="space-y-2">
                        <Label id="ip-select-label" htmlFor="ip-select">Intended Parent(s)</Label>
                        {!canViewIntendedParents && permissionsLoaded ? (
                            <Alert>
                                <AlertCircleIcon className="size-4" />
                                <AlertDescription>
                                    Your account does not have permission to view intended parents. Ask an admin to update your role or permissions.
                                </AlertDescription>
                            </Alert>
                        ) : (
                            // The trigger renders while the list loads so it can take initial focus.
                            <Popover open={isIpPickerOpen} onOpenChange={handleIpPickerOpenChange}>
                                <PopoverTrigger
                                    render={
                                        <Button
                                            ref={ipTriggerRef}
                                            id="ip-select"
                                            type="button"
                                            variant="outline"
                                            aria-haspopup="listbox"
                                            aria-labelledby="ip-select-label ip-select"
                                            className="w-full justify-between font-normal"
                                        >
                                            <span className={cn("truncate", !selectedIp && "text-muted-foreground")}>
                                                {selectedIp ? getIntendedParentLabel(selectedIp) : "Select intended parent(s)"}
                                            </span>
                                            <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
                                        </Button>
                                    }
                                />
                                <PopoverContent className="w-(--anchor-width) gap-0 p-0" align="start">
                                    <Command shouldFilter={false}>
                                        <CommandInput
                                            placeholder="Search intended parents"
                                            aria-label="Search intended parents"
                                            value={ipQuery}
                                            onValueChange={setIpQuery}
                                        />
                                        <CommandList className="max-h-60">
                                            {ipsLoading || permissionsQuery.isLoading ? (
                                                <div
                                                    role="status"
                                                    className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"
                                                >
                                                    <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                                    Loading&hellip;
                                                </div>
                                            ) : filteredIntendedParents.length === 0 ? (
                                                <CommandEmpty>No intended parents found</CommandEmpty>
                                            ) : (
                                                filteredIntendedParents.map((ip) => (
                                                    <CommandItem
                                                        key={ip.id}
                                                        value={ip.id}
                                                        onSelect={() => {
                                                            setSelectedIpId(ip.id)
                                                            handleIpPickerOpenChange(false)
                                                        }}
                                                    >
                                                        <span className="truncate font-medium">{getIntendedParentLabel(ip)}</span>
                                                        {ip.intended_parent_number && (
                                                            <span className="text-muted-foreground">#{ip.intended_parent_number}</span>
                                                        )}
                                                    </CommandItem>
                                                ))
                                            )}
                                        </CommandList>
                                    </Command>
                                </PopoverContent>
                            </Popover>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="notes">Notes (optional)</Label>
                        <Textarea
                            id="notes"
                            placeholder="Add any notes about this match proposal..."
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            className="min-h-24"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!canViewIntendedParents || !selectedIpId || createMatch.isPending}
                    >
                        {createMatch.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Propose Match
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
