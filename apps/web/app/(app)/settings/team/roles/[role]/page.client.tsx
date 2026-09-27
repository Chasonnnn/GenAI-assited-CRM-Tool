"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SaveBar } from "@/components/ui/save-bar"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Lock, Loader2 } from "lucide-react"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { useRoleDetail, useUpdateRolePermissions } from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"
import { toast } from "@/components/ui/toast"
import { SettingsPageGate } from "../../../settings-page-gate"

const CATEGORY_ORDER = [
    "Navigation",
    "Surrogates",
    "Intended Parents",
    "Tasks",
    "Team",
    "Settings",
    "Compliance",
]

// Keeps the existing destination (the roles list is this page's parent); only the label changed.
const ROLES_BACK_LINK = { href: "/settings/team/roles", label: "Back to Role Permissions" }

export default function RoleDetailPage() {
    return (
        <SettingsPageGate
            title="Role Permissions"
            permission="view_roles"
            deniedDescription="Role permissions need the View roles permission. Ask an admin to update your role."
            back={ROLES_BACK_LINK}
        >
            <RoleDetailContent />
        </SettingsPageGate>
    )
}

function RoleDetailContent() {
    const params = useParams()
    const rawRole = params.role
    const role = typeof rawRole === "string"
        ? rawRole
        : Array.isArray(rawRole)
            ? rawRole[0] ?? ""
            : ""
    const { data: roleDetail, isLoading, isError, error, refetch, isFetching } = useRoleDetail(role)
    const updatePermissions = useUpdateRolePermissions()
    const { user } = useAuth()

    const isDeveloper = user?.role === "developer"

    const [changes, setChanges] = useState<Record<string, boolean>>({})
    const hasChanges = Object.keys(changes).length > 0

    const originalPermissionValues = new Map<string, boolean>()
    for (const perms of Object.values(roleDetail?.permissions_by_category ?? {})) {
        for (const permission of perms) {
            originalPermissionValues.set(permission.key, permission.is_granted)
        }
    }

    const handleToggle = (permKey: string, newValue: boolean) => {
        setChanges(prev => {
            const originalValue = originalPermissionValues.get(permKey) ?? false

            if (newValue === originalValue) {
                const rest = { ...prev }
                delete rest[permKey]
                return rest
            }
            return { ...prev, [permKey]: newValue }
        })
    }

    const handleSave = async () => {
        try {
            await updatePermissions.mutateAsync({ role, permissions: changes })
            setChanges({})
            toast.success("Permissions updated")
        } catch (saveError) {
            const message = getActionErrorMessage(saveError, "Couldn't update permissions. Try again.")
            if (message) toast.error(message)
        }
    }

    if (isLoading || isError || !roleDetail) {
        return (
            <div className="flex min-h-screen flex-col">
                <PageHeader title="Role Permissions" back={ROLES_BACK_LINK} />
                {isLoading ? (
                    <div className="flex items-center justify-center p-12" role="status" aria-label="Loading">
                        <Loader2 className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : (
                    <QueryErrorState
                        error={error}
                        onRetry={() => void refetch()}
                        isRetrying={isFetching}
                        title="Couldn't load this role"
                        notFound={{
                            title: "Role not found",
                            backHref: ROLES_BACK_LINK.href,
                            backLabel: ROLES_BACK_LINK.label,
                        }}
                        headingLevel={2}
                    />
                )}
            </div>
        )
    }

    // Sort categories
    const sortedCategories = Object.keys(roleDetail.permissions_by_category).sort((a, b) => {
        const aIdx = CATEGORY_ORDER.indexOf(a)
        const bIdx = CATEGORY_ORDER.indexOf(b)
        if (aIdx === -1 && bIdx === -1) return a.localeCompare(b)
        if (aIdx === -1) return 1
        if (bIdx === -1) return -1
        return aIdx - bIdx
    })

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader
                title={`${roleDetail.label} Permissions`}
                back={ROLES_BACK_LINK}
                meta={
                    isDeveloper ? null : (
                        <Badge variant="outline">
                            <Lock className="size-3 mr-1" aria-hidden="true" />
                            Read only
                        </Badge>
                    )
                }
            />

            <div className="flex-1 space-y-6 p-6">
                {sortedCategories.map((category) => {
                    const permissions = roleDetail.permissions_by_category[category] ?? []

                    return (
                        <Card key={category}>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-lg">{category}</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    {permissions.map((perm) => {
                                        const currentValue = changes[perm.key] ?? perm.is_granted
                                        const isChanged = perm.key in changes

                                        return (
                                            <div
                                                key={perm.key}
                                                className={`flex items-center justify-between py-2 ${isChanged ? "bg-warning/10 -mx-2 px-2 rounded" : ""}`}
                                            >
                                                <div className="flex-1">
                                                    <Label className="font-medium flex items-center gap-2">
                                                        {perm.label}
                                                        {perm.developer_only && (
                                                            <Badge variant="outline" className="text-xs">
                                                                <Lock className="size-3 mr-1" aria-hidden="true" />
                                                                Dev Only
                                                            </Badge>
                                                        )}
                                                    </Label>
                                                    <p className="text-sm text-muted-foreground">
                                                        {perm.description}
                                                    </p>
                                                </div>
                                                <Switch
                                                    checked={currentValue}
                                                    onCheckedChange={(checked) => handleToggle(perm.key, checked)}
                                                    disabled={!isDeveloper || perm.developer_only}
                                                    aria-label={`${perm.label} permission`}
                                                />
                                            </div>
                                        )
                                    })}
                                </div>
                            </CardContent>
                        </Card>
                    )
                })}
            </div>

            {isDeveloper ? (
                <SaveBar
                    dirty={hasChanges}
                    changeCount={Object.keys(changes).length}
                    saving={updatePermissions.isPending}
                    onSave={() => void handleSave()}
                    onDiscard={() => setChanges({})}
                />
            ) : null}
        </div>
    )
}
