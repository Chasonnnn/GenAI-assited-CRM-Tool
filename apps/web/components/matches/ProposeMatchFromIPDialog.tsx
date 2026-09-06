"use client"

import { useQuery } from "@tanstack/react-query"
import { listDonors } from "@/lib/api/donors"
import type { DonorType } from "@/lib/types/donor"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2Icon, HeartHandshakeIcon, AlertCircleIcon } from "lucide-react"
import { toast } from "@/components/ui/toast"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useSurrogates } from "@/lib/hooks/use-surrogates"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import {
    getEligibleForMatchingStageLabel,
    isEligibleForMatchingCandidate,
} from "@/lib/match-pipeline-stage-utils"

interface ProposeMatchFromIPDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    intendedParentId: string
    ipName?: string
    onSuccess?: () => void
}

export function ProposeMatchFromIPDialog({
    open,
    onOpenChange,
    intendedParentId,
    ipName,
    onSuccess,
}: ProposeMatchFromIPDialogProps) {
    const [kind, setKind] = useState<"surrogate" | "donor">("surrogate")
    const [donorType, setDonorType] = useState<DonorType>("egg")
    const [selectedDonorId, setSelectedDonorId] = useState("")
    const donorQuery = useQuery({ queryKey: ["donors", "match-candidates", donorType], queryFn: () => listDonors({ donor_type: donorType, per_page: 100 }), enabled: open && kind === "donor" })
    const [selectedSurrogateId, setSelectedSurrogateId] = useState<string>("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)

    const { data: surrogatesData, isLoading: surrogatesLoading } = useSurrogates({
        per_page: 100
    })
    const { data: surrogatePipeline } = useDefaultPipeline("surrogate")
    const createMatch = useCreateMatch()

    const eligibleStageLabel = getEligibleForMatchingStageLabel(surrogatePipeline?.stages)
    const eligibleSurrogates = surrogatesData?.items
        ? surrogatesData.items.filter((surrogate) =>
            isEligibleForMatchingCandidate(surrogate, surrogatePipeline?.stages),
        )
        : []

    const handleSubmit = async () => {
        if (!(kind === "donor" ? selectedDonorId : selectedSurrogateId)) return
        setError(null)

        try {
            await createMatch.mutateAsync({
                ...(kind === "donor" ? { donor_id: selectedDonorId, match_kind: kind } : { surrogate_id: selectedSurrogateId }),
                intended_parent_id: intendedParentId,
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            toast.success("Match proposed successfully!")
            onOpenChange(false)
            setSelectedSurrogateId("")
            setSelectedDonorId("")
            setNotes("")
            onSuccess?.()
        } catch (e: unknown) {
            console.error("Failed to propose match:", e instanceof Error ? e.message : e)
            setError(e instanceof Error ? e.message : "Failed to propose match. Please try again.")
        }
    }

    const handleClose = () => {
        onOpenChange(false)
        setSelectedSurrogateId("")
        setSelectedDonorId("")
        setNotes("")
        setError(null)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <HeartHandshakeIcon className="size-5" />
                        {ipName ? `Propose match for ${ipName}` : "Propose Match"}
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
                        <Label htmlFor="match-kind">Match Kind</Label>
                        <Select value={kind} onValueChange={(value) => { if (value === "surrogate" || value === "donor") { setKind(value); setError(null) } }}>
                            <SelectTrigger id="match-kind"><SelectValue>{(value: string | null) => value === "donor" ? "Donor" : "Surrogate"}</SelectValue></SelectTrigger>
                            <SelectContent><SelectItem value="surrogate">Surrogate</SelectItem><SelectItem value="donor">Donor</SelectItem></SelectContent>
                        </Select>
                    </div>
                    {kind === "donor" ? <>
                        <div className="space-y-2">
                            <Label htmlFor="match-donor-type">Donor Type</Label>
                            <Select value={donorType} onValueChange={(value) => { if (value === "egg" || value === "sperm") { setDonorType(value); setSelectedDonorId("") } }}>
                                <SelectTrigger id="match-donor-type"><SelectValue>{(value: string | null) => value === "sperm" ? "Sperm Donor" : "Egg Donor"}</SelectValue></SelectTrigger>
                                <SelectContent><SelectItem value="egg">Egg Donor</SelectItem><SelectItem value="sperm">Sperm Donor</SelectItem></SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="match-donor">Donor</Label>
                            {donorQuery.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading donors…</p> : donorQuery.isError ? <p role="alert" className="text-sm text-destructive">Unable to load donors</p> : !donorQuery.data?.items.length ? <p className="text-sm text-muted-foreground">No donors found</p> : <Select value={selectedDonorId} onValueChange={(value) => setSelectedDonorId(value ?? "")}>
                                <SelectTrigger id="match-donor"><SelectValue>{(value: string | null) => donorQuery.data?.items.find((donor) => donor.id === value)?.full_name ?? "Select a donor"}</SelectValue></SelectTrigger>
                                <SelectContent>{donorQuery.data.items.map((donor) => <SelectItem value={donor.id} key={donor.id}>{donor.full_name} #{donor.donor_number}</SelectItem>)}</SelectContent>
                            </Select>}
                        </div>
                    </> : (
                    <div className="space-y-2">
                        <Label htmlFor="surrogate-select">{`Surrogate (${eligibleStageLabel} Only)`}</Label>
                        {surrogatesLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading available surrogates&hellip;
                            </div>
                        ) : eligibleSurrogates.length === 0 ? (
                            <div className="text-sm text-muted-foreground p-3 border rounded-md bg-muted/30">
                                {`No surrogates are currently in "${eligibleStageLabel}" status.`}
                            </div>
                        ) : (
                            <Select value={selectedSurrogateId} onValueChange={(v) => setSelectedSurrogateId(v || "")}>
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select a surrogate">{(value: string | null) => eligibleSurrogates.find((surrogate) => surrogate.id === value)?.full_name ?? "Select a surrogate"}</SelectValue>
                                </SelectTrigger>
                                <SelectContent className="max-h-[300px]">
                                    {eligibleSurrogates.map((s) => (
                                        <SelectItem key={s.id} value={s.id} className="py-2">
                                            <span className="font-medium">{s.full_name || "Unknown"}</span>
                                            <span className="text-muted-foreground ml-2">#{s.surrogate_number}</span>
                                            {s.state && <span className="text-muted-foreground ml-2">• {s.state}</span>}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    )}

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
                        disabled={!(kind === "donor" ? selectedDonorId : selectedSurrogateId) || createMatch.isPending}
                    >
                        {createMatch.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Propose Match
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
