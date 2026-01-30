"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateAiTab } from "@/components/surrogates/detail/SurrogateAiTab"
import { useSummarizeSurrogate, useDraftEmail, useAISettings } from "@/lib/hooks/use-ai"
import type { DraftEmailResponse, EmailType, SummarizeSurrogateResponse } from "@/lib/api/ai"

export default function SurrogateAiPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const summarizeSurrogateMutation = useSummarizeSurrogate()
    const draftEmailMutation = useDraftEmail()
    const { data: aiSettings } = useAISettings()

    const [aiSummary, setAiSummary] = React.useState<SummarizeSurrogateResponse | null>(null)
    const [aiDraftEmail, setAiDraftEmail] = React.useState<DraftEmailResponse | null>(null)
    const [selectedEmailType, setSelectedEmailType] = React.useState<EmailType | null>(null)

    const handleGenerateSummary = async () => {
        const result = await summarizeSurrogateMutation.mutateAsync(id)
        setAiSummary(result)
    }

    const handleDraftEmail = async () => {
        if (!selectedEmailType) return
        const result = await draftEmailMutation.mutateAsync({
            surrogate_id: id,
            email_type: selectedEmailType,
        })
        setAiDraftEmail(result)
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
                isGeneratingSummary={summarizeSurrogateMutation.isPending}
                isDraftingEmail={draftEmailMutation.isPending}
            />
        </TabsContent>
    )
}
