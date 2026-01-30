"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateInterviewTab } from "@/components/surrogates/interviews/SurrogateInterviewTab"

export default function SurrogateInterviewsPage() {
    const params = useParams<{ id: string }>()
    const id = params.id

    return (
        <TabsContent value="interviews" className="space-y-4">
            <SurrogateInterviewTab surrogateId={id} />
        </TabsContent>
    )
}
