"use client"

import { useAuth } from "@/lib/auth-context"
import { isPermissionError } from "@/lib/error-utils"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"

export type PermissionCheck = {
    /** Auth or effective permissions are still loading; render a loading state, not a denied one. */
    isLoading: boolean
    /**
     * The permissions lookup failed (500, network) and no earlier result exists. Render
     * LoadErrorState with `retry` instead of the denied state: the viewer may hold the permission.
     * A 403 on the lookup is not an error here; `can` then denies.
     */
    isError: boolean
    /** Refetches the permissions lookup. */
    retry: () => void
    /** Pass to LoadErrorState `isRetrying`: a failed lookup keeps isError while it refetches. */
    isRetrying: boolean
    /** True when the viewer holds `permission`; use the same key the API route requires. */
    can: (permission: string) => boolean
}

/**
 * Gates pages, nav items, tabs and actions on the permission keys the API enforces.
 * Developers hold every permission (the API grants them all), matching the sidebar's rule.
 * Page gate: isLoading → loading, isError → LoadErrorState, !can(key) → PermissionDeniedState.
 */
export function usePermissionCheck(): PermissionCheck {
    const { user, isLoading: authLoading } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const isDeveloper = user?.role === "developer"
    const needsLookup = !isDeveloper && Boolean(user)
    const permissions = permissionsQuery.data?.permissions ?? []

    return {
        isLoading: authLoading || (needsLookup && permissionsQuery.isLoading),
        isError:
            !authLoading &&
            needsLookup &&
            Boolean(permissionsQuery.isError) &&
            permissionsQuery.data === undefined &&
            !isPermissionError(permissionsQuery.error),
        retry: () => {
            void permissionsQuery.refetch()
        },
        isRetrying: needsLookup && Boolean(permissionsQuery.isFetching),
        can: (permission) => isDeveloper || permissions.includes(permission),
    }
}
