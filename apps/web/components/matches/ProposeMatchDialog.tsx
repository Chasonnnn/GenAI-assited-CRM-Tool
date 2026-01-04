"use client"

import { useState } from "react"
import { UsersIcon } from "lucide-react"
import { MatchProposalDialog } from "@/components/matches/MatchProposalDialog"
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

    const { data: ipsData, isLoading: ipsLoading } = useIntendedParents({ per_page: 100 })
    const createMatch = useCreateMatch()

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            setSelectedIpId("")
        }
        onOpenChange(nextOpen)
    }

    const handleSubmit = async (payload: { compatibilityScore?: number; notes?: string }) => {
        if (!selectedIpId) return

        await createMatch.mutateAsync({
            case_id: caseId,
            intended_parent_id: selectedIpId,
            compatibility_score: payload.compatibilityScore,
            notes: payload.notes,
        })
        alert("Match proposed successfully!")
        onSuccess?.()
    }

    const ipOptions = ipsData?.items.map((ip) => ({
        value: ip.id,
        label: ip.full_name || ip.email || "Unknown",
    })) || []

    return (
        <MatchProposalDialog
            open={open}
            onOpenChange={handleOpenChange}
            title="Propose Match"
            description={caseName ? `Create a match proposal for ${caseName}` : "Create a match proposal for this surrogate"}
            icon={<UsersIcon className="size-5" />}
            selectLabel="Intended Parent(s)"
            selectPlaceholder="Select intended parent(s)"
            options={ipOptions}
            selectedValue={selectedIpId}
            onSelectedValueChange={(value) => setSelectedIpId(value || "")}
            isLoading={ipsLoading}
            loadingText="Loading..."
            submitDisabled={!selectedIpId}
            isSubmitting={createMatch.isPending}
            dialogClassName="max-w-md"
            onSubmit={handleSubmit}
        />
    )
}
