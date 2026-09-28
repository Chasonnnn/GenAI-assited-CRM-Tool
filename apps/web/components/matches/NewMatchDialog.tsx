"use client"

import { useRef, useState } from "react"
import type { Route } from "next"
import { useRouter } from "next/navigation"
import { AlertCircleIcon, Loader2Icon } from "lucide-react"

import { showMatchProposedToast } from "@/components/matches/match-proposed-toast"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useSurrogates } from "@/lib/hooks/use-surrogates"
import {
    getEligibleForMatchingStageId,
    getEligibleForMatchingStageLabel,
    isEligibleForMatchingCandidate,
} from "@/lib/match-pipeline-stage-utils"

type NewMatchDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
}

/** Proposes a surrogate match from the Matches list. Mount it only while open. */
export function NewMatchDialog({ open, onOpenChange }: NewMatchDialogProps) {
    const router = useRouter()
    const [selectedSurrogateId, setSelectedSurrogateId] = useState("")
    const [selectedIpId, setSelectedIpId] = useState("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)
    const popupRef = useRef<HTMLDivElement | null>(null)
    const surrogateTriggerRef = useRef<HTMLButtonElement | null>(null)

    const { data: surrogatePipeline, isLoading: pipelineLoading } = useDefaultPipeline("surrogate")
    const eligibleStageId = getEligibleForMatchingStageId(surrogatePipeline?.stages)
    const { data: surrogatesData, isLoading: surrogatesQueryLoading } = useSurrogates(
        { per_page: 100, ...(eligibleStageId ? { stage_id: eligibleStageId } : {}) },
        { enabled: Boolean(eligibleStageId) },
    )
    const surrogatesLoading = pipelineLoading || surrogatesQueryLoading
    const { data: ipsData, isLoading: ipsLoading } = useIntendedParents({ per_page: 100 })
    const createMatch = useCreateMatch()

    const eligibleStageLabel = getEligibleForMatchingStageLabel(surrogatePipeline?.stages)
    const eligibleSurrogates =
        surrogatesData?.items?.filter((surrogate) =>
            isEligibleForMatchingCandidate(surrogate, surrogatePipeline?.stages),
        ) ?? []

    const close = () => {
        onOpenChange(false)
        setSelectedSurrogateId("")
        setSelectedIpId("")
        setNotes("")
        setError(null)
    }

    const handleSubmit = async () => {
        if (!selectedSurrogateId || !selectedIpId) return
        setError(null)
        try {
            const match = await createMatch.mutateAsync({
                surrogate_id: selectedSurrogateId,
                intended_parent_id: selectedIpId,
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            close()
            showMatchProposedToast(match, (href) => router.push(href as Route))
        } catch (e: unknown) {
            setError(getActionErrorMessage(e, "Couldn't create match. Try again."))
        }
    }

    return (
        <Dialog open={open} onOpenChange={(next) => { if (!next) close() }}>
            <DialogContent
                size="md"
                ref={popupRef}
                // The surrogate picker renders after its list loads. Until then, focus the dialog
                // itself; the default first tabbable would be Notes.
                initialFocus={() => surrogateTriggerRef.current ?? popupRef.current}
            >
                <DialogHeader>
                    <DialogTitle>New Match</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    {error ? (
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" aria-hidden="true" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    ) : null}

                    <div className="space-y-2">
                        <Label htmlFor="new-match-surrogate">{`Surrogate (${eligibleStageLabel} Only)`}</Label>
                        {surrogatesLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                Loading surrogates&hellip;
                            </div>
                        ) : eligibleSurrogates.length === 0 ? (
                            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
                                {`No surrogates are currently in "${eligibleStageLabel}" status.`}
                            </div>
                        ) : (
                            <Select value={selectedSurrogateId} onValueChange={(value) => setSelectedSurrogateId(value || "")}>
                                <SelectTrigger id="new-match-surrogate" ref={surrogateTriggerRef} className="w-full">
                                    <SelectValue placeholder="Select a surrogate">
                                        {(value: string | null) =>
                                            eligibleSurrogates.find((surrogate) => surrogate.id === value)?.full_name ??
                                            "Select a surrogate"}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent className="max-h-[200px]">
                                    {eligibleSurrogates.map((surrogate) => (
                                        <SelectItem key={surrogate.id} value={surrogate.id}>
                                            <span className="font-medium">{surrogate.full_name || "Unknown"}</span>
                                            <span className="ml-2 text-muted-foreground">#{surrogate.surrogate_number}</span>
                                            {surrogate.state ? (
                                                <span className="ml-2 text-muted-foreground">• {surrogate.state}</span>
                                            ) : null}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="new-match-intended-parent">Intended Parents</Label>
                        {ipsLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                Loading intended parents&hellip;
                            </div>
                        ) : (
                            <Select value={selectedIpId} onValueChange={(value) => setSelectedIpId(value || "")}>
                                <SelectTrigger id="new-match-intended-parent" className="w-full">
                                    <SelectValue placeholder="Select intended parents">
                                        {(value: string | null) =>
                                            ipsData?.items.find((ip) => ip.id === value)?.full_name ??
                                            "Select intended parents"}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent className="max-h-[200px]">
                                    {ipsData?.items?.map((ip) => (
                                        <SelectItem key={ip.id} value={ip.id}>
                                            <span className="font-medium">{ip.full_name || ip.email || "Unknown"}</span>
                                            {ip.intended_parent_number ? (
                                                <span className="ml-2 text-muted-foreground">#{ip.intended_parent_number}</span>
                                            ) : null}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="new-match-notes">Notes (optional)</Label>
                        <Textarea
                            id="new-match-notes"
                            value={notes}
                            onChange={(event) => setNotes(event.target.value)}
                            className="min-h-20"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={close}>
                        Cancel
                    </Button>
                    <Button
                        onClick={() => { void handleSubmit() }}
                        disabled={!selectedSurrogateId || !selectedIpId || createMatch.isPending}
                    >
                        {createMatch.isPending ? <Loader2Icon className="mr-2 size-4 animate-spin" aria-hidden="true" /> : null}
                        Create Match
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
