"use client"

import { useParams } from "next/navigation"
import { PermissionMemberDetail } from "@/components/permissions/permission-member-detail"

export default function MemberDetailPage() {
    const params = useParams<{ id: string }>()
    return <PermissionMemberDetail key={params.id} memberId={params.id} />
}
