"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateJourneyTab } from "@/components/surrogates/journey/SurrogateJourneyTab"

export default function SurrogateJourneyPage() {
    const params = useParams<{ id: string }>()
    const id = params.id

    return (
        <TabsContent value="journey" className="space-y-4">
            <SurrogateJourneyTab surrogateId={id} />
        </TabsContent>
    )
}
