"use client"

import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"

export type PermissionCheck = {
    /** Auth or effective permissions are still loading; render a loading state, not a denied one. */
    isLoading: boolean
    /** True when the viewer holds `permission`; use the same key the API route requires. */
    can: (permission: string) => boolean
}

/**
 * Gates pages, nav items, tabs and actions on the permission keys the API enforces.
 * Developers hold every permission (the API grants them all), matching the sidebar's rule.
 */
export function usePermissionCheck(): PermissionCheck {
    const { user, isLoading: authLoading } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const isDeveloper = user?.role === "developer"
    const permissions = permissionsQuery.data?.permissions ?? []

    return {
        isLoading: authLoading || (!isDeveloper && Boolean(user) && permissionsQuery.isLoading),
        can: (permission) => isDeveloper || permissions.includes(permission),
    }
}
