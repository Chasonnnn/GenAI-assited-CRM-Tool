"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { ProfileCard } from "@/components/surrogates/profile/ProfileCard"
import { useAuth } from "@/lib/auth-context"

export default function SurrogateProfilePage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { user } = useAuth()
    const canViewProfile = user
        ? ["case_manager", "admin", "developer"].includes(user.role)
        : false

    if (!canViewProfile) {
        return null
    }

    return (
        <TabsContent value="profile" className="space-y-4">
            <ProfileCard surrogateId={id} />
        </TabsContent>
    )
}
