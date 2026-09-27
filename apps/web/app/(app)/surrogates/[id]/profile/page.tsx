"use client"

import { TabsContent } from "@/components/ui/tabs"
import { ProfileCard } from "@/components/surrogates/profile/ProfileCard"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout/context"

export default function SurrogateProfilePage() {
    const { surrogateId, canViewProfile, canEditSurrogate } = useSurrogateDetailData()

    if (!canViewProfile) {
        return null
    }

    return (
        <TabsContent value="profile" className="space-y-4">
            <ProfileCard surrogateId={surrogateId} readOnly={canEditSurrogate === false} />
        </TabsContent>
    )
}
