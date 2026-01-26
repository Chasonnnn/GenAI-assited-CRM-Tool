"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { ChevronLeft, Shield, Lock, Loader2, Save, AlertTriangle } from "lucide-react"
import { useRoleDetail, useUpdateRolePermissions } from "@/lib/hooks/use-permissions"
import { NotFoundState } from "@/components/not-found-state"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"

const CATEGORY_ORDER = [
    "Navigation",
    "Surrogates",
    "Intended Parents",
    "Tasks",
    "Team",
    "Settings",
    "Compliance",
]

export default function RoleDetailPage() {
    const params = useParams()
    const rawRole = params.role
    const role = typeof rawRole === "string"
        ? rawRole
        : Array.isArray(rawRole)
            ? rawRole[0] ?? ""
            : ""
    const { data: roleDetail, isLoading } = useRoleDetail(role)
    const updatePermissions = useUpdateRolePermissions()
    const { user } = useAuth()

    const isDeveloper = user?.role === "developer"

    const [changes, setChanges] = useState<Record<string, boolean>>({})
    const hasChanges = Object.keys(changes).length > 0

    const handleToggle = (permKey: string, newValue: boolean) => {
        setChanges(prev => {
            const original = roleDetail?.permissions_by_category
            let originalValue = false
            if (original) {
                for (const perms of Object.values(original)) {
                    const found = perms.find(p => p.key === permKey)
                    if (found) {
                        originalValue = found.is_granted
                        break
                    }
                }
            }

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
        } catch (error) {
            toast.error(
                "Failed to update permissions",
                { description: error instanceof Error ? error.message : "Unknown error" }
            )
        }
    }

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!roleDetail) {
        return (
            <NotFoundState
                title="Role not found"
                backUrl="/settings/team/roles"
            />
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
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="sm" render={<Link href="/settings/team/roles" />}>
                        <ChevronLeft className="size-4 mr-1" />
                        Back
                    </Button>
                </div>
                {isDeveloper && hasChanges && (
                    <Button onClick={handleSave} disabled={updatePermissions.isPending}>
                        {updatePermissions.isPending ? (
                            <Loader2 className="size-4 mr-2 animate-spin" />
                        ) : (
                            <Save className="size-4 mr-2" />
                        )}
                        Save Changes
                    </Button>
                )}
            </div>

            <div>
                <h1 className="text-2xl font-semibold flex items-center gap-2">
                    <Shield className="size-6" />
                    {roleDetail.label} Permissions
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    {isDeveloper
                        ? "Toggle permissions on/off to customize this role's default access."
                        : "View default permissions for this role. Only Developers can modify."}
                </p>
            </div>

            {hasChanges && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
                    <AlertTriangle className="size-5 text-yellow-600" />
                    <p className="text-sm text-yellow-800">
                        You have unsaved changes. Click Save Changes to apply.
                    </p>
                </div>
            )}

            <div className="space-y-6">
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
                                                className={`flex items-center justify-between py-2 ${isChanged ? "bg-yellow-50 -mx-2 px-2 rounded" : ""}`}
                                            >
                                                <div className="flex-1">
                                                    <Label className="font-medium flex items-center gap-2">
                                                        {perm.label}
                                                        {perm.developer_only && (
                                                            <Badge variant="outline" className="text-xs">
                                                                <Lock className="size-3 mr-1" />
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
        </div>
    )
}
