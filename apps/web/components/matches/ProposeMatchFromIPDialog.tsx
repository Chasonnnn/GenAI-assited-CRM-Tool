"use client"

import { useState, useMemo } from "react"
import { HeartHandshakeIcon } from "lucide-react"
import { MatchProposalDialog } from "@/components/matches/MatchProposalDialog"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useCases } from "@/lib/hooks/use-cases"

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
    const [selectedCaseId, setSelectedCaseId] = useState<string>("")

    // Fetch cases for pending_match filtering
    const { data: casesData, isLoading: casesLoading } = useCases({
        per_page: 100
    })
    const createMatch = useCreateMatch()

    // Filter to only pending_match cases via stage_slug
    const eligibleCases = useMemo(() => {
        if (!casesData?.items) return []
        return casesData.items.filter((c) => c.stage_slug === "pending_match")
    }, [casesData])

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            setSelectedCaseId("")
        }
        onOpenChange(nextOpen)
    }

    const handleSubmit = async (payload: { compatibilityScore?: number; notes?: string }) => {
        if (!selectedCaseId) return

        await createMatch.mutateAsync({
            case_id: selectedCaseId,
            intended_parent_id: intendedParentId,
            compatibility_score: payload.compatibilityScore,
            notes: payload.notes,
        })
        alert("Match proposed successfully!")
        onSuccess?.()
    }

    const caseOptions = eligibleCases.map((c) => ({
        value: c.id,
        label: (
            <>
                <span className="font-medium">{c.full_name || "Unknown"}</span>
                <span className="text-muted-foreground ml-2">#{c.case_number}</span>
                {c.state && <span className="text-muted-foreground ml-2">• {c.state}</span>}
            </>
        ),
        itemClassName: "py-2",
    }))

    return (
        <MatchProposalDialog
            open={open}
            onOpenChange={handleOpenChange}
            title="Propose Match"
            description={ipName ? `Create a match proposal for ${ipName}` : "Create a match proposal for this intended parent"}
            icon={<HeartHandshakeIcon className="size-5" />}
            selectLabel="Surrogate (Pending Match Only)"
            selectPlaceholder="Select a surrogate"
            options={caseOptions}
            selectedValue={selectedCaseId}
            onSelectedValueChange={(value) => setSelectedCaseId(value || "")}
            isLoading={casesLoading}
            loadingText="Loading available surrogates..."
            emptyState={(
                <div className="text-sm text-muted-foreground p-3 border rounded-md bg-muted/30">
                    No surrogates are currently in "Pending Match" status.
                </div>
            )}
            submitDisabled={!selectedCaseId}
            isSubmitting={createMatch.isPending}
            submitClassName="bg-teal-600 hover:bg-teal-700"
            dialogClassName="max-w-lg"
            selectTriggerClassName="w-full"
            selectContentClassName="max-h-[300px]"
            onSubmit={handleSubmit}
        />
    )
}
