"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateHistoryTab } from "@/components/surrogates/detail/SurrogateHistoryTab"
import { useSurrogateActivity } from "@/lib/hooks/use-surrogates"
import { formatDateTime } from "@/components/surrogates/detail/surrogate-detail-utils"

export default function SurrogateHistoryPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { data: activityData } = useSurrogateActivity(id)

    return (
        <TabsContent value="history" className="space-y-4">
            <SurrogateHistoryTab
                activities={activityData?.items ?? []}
                formatDateTime={formatDateTime}
            />
        </TabsContent>
    )
}
