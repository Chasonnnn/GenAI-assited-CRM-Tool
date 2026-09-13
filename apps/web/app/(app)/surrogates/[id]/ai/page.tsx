"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateAiTab } from "@/components/surrogates/detail/SurrogateAiTab"
import { useSummarizeSurrogate, useDraftEmail, useAIAvailability } from "@/lib/hooks/use-ai"
import type { DraftEmailResponse, EmailType, SummarizeSurrogateResponse } from "@/lib/api/ai"

export default function SurrogateAiPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const summarizeSurrogateMutation = useSummarizeSurrogate()
    const draftEmailMutation = useDraftEmail()
    const availability = useAIAvailability()
    const aiSettings = availability.data

    const [aiSummary, setAiSummary] = React.useState<SummarizeSurrogateResponse | null>(null)
    const [aiDraftEmail, setAiDraftEmail] = React.useState<DraftEmailResponse | null>(null)
    const [selectedEmailType, setSelectedEmailType] = React.useState<EmailType | null>(null)

    const handleGenerateSummary = async () => {
        if (!aiSettings?.is_enabled) return
        const result = await summarizeSurrogateMutation.mutateAsync(id)
        setAiSummary(result)
    }

    const handleDraftEmail = async () => {
        if (!selectedEmailType || !aiSettings?.is_enabled) return
        const result = await draftEmailMutation.mutateAsync({
            surrogate_id: id,
            email_type: selectedEmailType,
        })
        setAiDraftEmail(result)
    }

    if (availability.isPending) {
        return <TabsContent value="ai"><p role="status">Loading AI Assistant…</p></TabsContent>
    }
    if (availability.isError) {
        return <TabsContent value="ai"><p role="alert">AI Assistant unavailable</p><Button variant="outline" onClick={() => void availability.refetch()}>Retry</Button></TabsContent>
    }

    return (
        <TabsContent value="ai" className="space-y-4">
            <SurrogateAiTab
                aiSettings={aiSettings}
                aiSummary={aiSummary}
                aiDraftEmail={aiDraftEmail}
                selectedEmailType={selectedEmailType}
                onSelectEmailType={setSelectedEmailType}
                onGenerateSummary={handleGenerateSummary}
                onDraftEmail={handleDraftEmail}
                summaryStatus={summarizeSurrogateMutation.isPending ? "generating" : "idle"}
                draftEmailStatus={draftEmailMutation.isPending ? "drafting" : "idle"}
            />
        </TabsContent>
    )
}
