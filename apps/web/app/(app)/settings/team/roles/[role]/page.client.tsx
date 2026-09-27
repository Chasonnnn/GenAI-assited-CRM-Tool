"use client"

import { useParams } from "next/navigation"
import { PermissionWorkspace } from "@/components/permissions/permission-workspace"

export default function RolePermissionPage() {
    const params = useParams<{ role: string }>()
    return <PermissionWorkspace key={params.role} initialRole={params.role} />
}
