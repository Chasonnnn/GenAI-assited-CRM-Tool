"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Loader2Icon, UsersIcon } from "lucide-react"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"

interface ProposeMatchDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    caseId: string
    caseName?: string
    onSuccess?: () => void
}

export function ProposeMatchDialog({
    open,
    onOpenChange,
    caseId,
    caseName,
    onSuccess,
}: ProposeMatchDialogProps) {
    const [selectedIpId, setSelectedIpId] = useState<string>("")
    const [compatibilityScore, setCompatibilityScore] = useState<string>("")
    const [notes, setNotes] = useState("")

    const { data: ipsData, isLoading: ipsLoading } = useIntendedParents({ per_page: 100 })
    const createMatch = useCreateMatch()

    const handleSubmit = async () => {
        if (!selectedIpId) return

        try {
            await createMatch.mutateAsync({
                case_id: caseId,
                intended_parent_id: selectedIpId,
                compatibility_score: compatibilityScore ? parseFloat(compatibilityScore) : undefined,
                notes: notes || undefined,
            })
            onOpenChange(false)
            setSelectedIpId("")
            setCompatibilityScore("")
            setNotes("")
            onSuccess?.()
        } catch (e) {
            // Error handled by mutation
        }
    }

    const handleClose = () => {
        onOpenChange(false)
        setSelectedIpId("")
        setCompatibilityScore("")
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
                        {caseName ? `Create a match proposal for ${caseName}` : "Create a match proposal for this surrogate"}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="ip-select">Intended Parent(s)</Label>
                        {ipsLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading...
                            </div>
                        ) : (
                            <Select value={selectedIpId} onValueChange={setSelectedIpId}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select intended parent(s)" />
                                </SelectTrigger>
                                <SelectContent>
                                    {ipsData?.items.map((ip) => (
                                        <SelectItem key={ip.id} value={ip.id}>
                                            {ip.full_name || ip.email || "Unknown"}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="score">Compatibility Score (optional)</Label>
                        <Input
                            id="score"
                            type="number"
                            min="0"
                            max="100"
                            placeholder="0-100"
                            value={compatibilityScore}
                            onChange={(e) => setCompatibilityScore(e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">Enter a score between 0-100 if applicable</p>
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
