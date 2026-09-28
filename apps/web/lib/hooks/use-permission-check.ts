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
    /** True when the viewer's effective permissions include `permission`; use the key the API route requires. */
    can: (permission: string) => boolean
    /**
     * The organization's permission policy version from the lookup; undefined until it loads.
     * Some surfaces use different keys per version (for example create_* under v2, edit_* under v1).
     */
    policyVersion?: number | undefined
}

/**
 * Gates pages, nav items, tabs and actions on the effective permission keys the API enforces.
 * The keys come from /settings/permissions/effective/me, which already applies the policy
 * version's rules (the v1 shim or v2), so `can` needs no version logic of its own.
 * Page gate: isLoading → loading, isError → LoadErrorState, !can(key) → PermissionDeniedState.
 */
export function usePermissionCheck(): PermissionCheck {
    const { user, isLoading: authLoading } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const isDeveloper = user?.role === "developer"
    const needsLookup = !isDeveloper && Boolean(user)
    const effective = permissionsQuery.data
    const permissions = effective?.permissions ?? []

    return {
        isLoading: authLoading || (needsLookup && permissionsQuery.isLoading),
        isError:
            !authLoading &&
            needsLookup &&
            Boolean(permissionsQuery.isError) &&
            effective === undefined &&
            !isPermissionError(permissionsQuery.error),
        retry: () => {
            void permissionsQuery.refetch()
        },
        isRetrying: needsLookup && Boolean(permissionsQuery.isFetching),
        // Developers do not wait for the lookup. Once it loads, its list is authoritative for
        // them too: under policy v2 the API withholds AI keys from developers when AI is off.
        can: (permission) =>
            isDeveloper && effective === undefined ? true : permissions.includes(permission),
        policyVersion: effective?.policy_version,
    }
}
