"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircleIcon, Loader2Icon, UsersIcon } from "lucide-react"
import { toast } from "sonner"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"

interface ProposeMatchDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateId: string
    surrogateName?: string
    onSuccess?: () => void
}

export function ProposeMatchDialog({
    open,
    onOpenChange,
    surrogateId,
    surrogateName,
    onSuccess,
}: ProposeMatchDialogProps) {
    const [selectedIpId, setSelectedIpId] = useState<string>("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)

    const { data: ipsData, isLoading: ipsLoading } = useIntendedParents({ per_page: 100 })
    const createMatch = useCreateMatch()

    const handleSubmit = async () => {
        if (!selectedIpId) return
        setError(null)

        try {
            await createMatch.mutateAsync({
                surrogate_id: surrogateId,
                intended_parent_id: selectedIpId,
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            toast.success("Match proposed successfully!")
            onOpenChange(false)
            setSelectedIpId("")
            setNotes("")
            onSuccess?.()
        } catch (e: unknown) {
            console.error("Failed to propose match:", e instanceof Error ? e.message : e)
            setError(e instanceof Error ? e.message : "Failed to propose match. Please try again.")
        }
    }

    const handleClose = () => {
        onOpenChange(false)
        setSelectedIpId("")
        setNotes("")
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" />
                        Propose Match
                    </DialogTitle>
                    <DialogDescription>
                        {surrogateName ? `Create a match proposal for ${surrogateName}` : "Create a match proposal for this surrogate"}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {error && (
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                    <div className="space-y-2">
                        <Label htmlFor="ip-select">Intended Parent(s)</Label>
                        {ipsLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading...
                            </div>
                        ) : (
                            <Select value={selectedIpId} onValueChange={(v) => setSelectedIpId(v || "")}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select intended parent(s)" />
                                </SelectTrigger>
                                <SelectContent>
                                    {ipsData?.items.map((ip) => (
                                        <SelectItem key={ip.id} value={ip.id}>
                                            <span className="font-medium">{ip.full_name || ip.email || "Unknown"}</span>
                                            {ip.intended_parent_number && (
                                                <span className="text-muted-foreground ml-2">#{ip.intended_parent_number}</span>
                                            )}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
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
                        disabled={!selectedIpId || createMatch.isPending}
                    >
                        {createMatch.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Propose Match
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
