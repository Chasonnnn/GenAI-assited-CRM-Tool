"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { Card, CardContent } from "@/components/ui/card"
import { SurrogateJourneyTab } from "@/components/surrogates/journey/SurrogateJourneyTab"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout"

export default function SurrogateJourneyPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { canViewJourney } = useSurrogateDetailData()

    if (!canViewJourney) {
        return (
            <TabsContent value="journey" className="space-y-4">
                <Card>
                    <CardContent className="py-12 text-center">
                        <p className="text-sm font-medium text-muted-foreground">
                            No journey available yet
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground/80">
                            Journey becomes available after Match Confirmed.
                        </p>
                    </CardContent>
                </Card>
            </TabsContent>
        )
    }

    return (
        <TabsContent value="journey" className="space-y-4">
            <SurrogateJourneyTab surrogateId={id} />
        </TabsContent>
    )
}
