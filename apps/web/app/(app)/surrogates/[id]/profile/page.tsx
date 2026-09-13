"use client"

import { TabsContent } from "@/components/ui/tabs"
import { SurrogateProfileCard } from "@/components/surrogates/SurrogateProfileCard"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout/context"

export default function SurrogateProfilePage() {
    const { surrogateId, canViewProfile, canEditSurrogate } = useSurrogateDetailData()

    if (!canViewProfile) {
        return null
    }

    return (
        <TabsContent value="profile" className="space-y-4">
            <SurrogateProfileCard surrogateId={surrogateId} readOnly={canEditSurrogate === false} />
        </TabsContent>
    )
}
