"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateInterviewTab } from "@/components/surrogates/interviews/SurrogateInterviewTab"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout/context"

export default function SurrogateInterviewsPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { canEditSurrogate, effectivePermissions } = useSurrogateDetailData()
    const isV2 = effectivePermissions?.policy_version === 2

    return (
        <TabsContent value="interviews" className="space-y-4">
            <SurrogateInterviewTab
                surrogateId={id}
                editPermission={isV2 ? canEditSurrogate : undefined}
                canUseAI={!isV2 || effectivePermissions.permissions.includes("use_ai_assistant")}
            />
        </TabsContent>
    )
}
