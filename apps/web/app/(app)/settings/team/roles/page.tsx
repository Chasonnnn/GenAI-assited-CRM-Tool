import { PermissionWorkspace } from "@/components/permissions/permission-workspace"

export default async function RolePermissionsPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
    const { tab } = await searchParams
    return <PermissionWorkspace key={tab} initialTab={tab === "check" || tab === "upgrade" ? tab : "roles"} />
}
