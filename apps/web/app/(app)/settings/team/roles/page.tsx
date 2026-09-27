"use client"

import Link from "@/components/app-link"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ChevronRight, Lock, Loader2 } from "lucide-react"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { useRoles } from "@/lib/hooks/use-permissions"
import type { RoleSummary } from "@/lib/api/permissions"
import { useAuth } from "@/lib/auth-context"
import { SettingsPageGate } from "../../settings-page-gate"

const ROLE_DESCRIPTIONS: Record<string, string> = {
    intake_specialist: "Entry-level role for processing new leads and initial case intake",
    case_manager: "Mid-level role for managing post-approval cases and matching",
    admin: "Admin role with team management and organization settings",
    developer: "Full access to all features including system configuration",
}

const ROLE_ICONS: Record<string, string> = {
    intake_specialist: "👤",
    case_manager: "📋",
    admin: "👔",
    developer: "🔧",
}

const TEAM_BACK_LINK = { href: "/settings/team", label: "Back to Team" }

export default function RolePermissionsPage() {
    return (
        <SettingsPageGate
            title="Role Permissions"
            permission="view_roles"
            deniedDescription="Role permissions need the View roles permission. Ask an admin to update your role."
            back={TEAM_BACK_LINK}
        >
            <RolePermissionsContent />
        </SettingsPageGate>
    )
}

function RolePermissionsContent() {
    const { data: roles, isLoading, isError, error, refetch, isFetching } = useRoles()
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader title="Role Permissions" back={TEAM_BACK_LINK} />
            <div className="p-6">
                {isLoading ? (
                    <div className="flex items-center justify-center p-12" role="status" aria-label="Loading">
                        <Loader2 className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : isError ? (
                    <QueryErrorState
                        error={error}
                        onRetry={() => void refetch()}
                        isRetrying={isFetching}
                        title="Couldn't load roles"
                        headingLevel={2}
                    />
                ) : (
                    <RoleCards roles={roles ?? []} isDeveloper={isDeveloper} />
                )}
            </div>
        </div>
    )
}

function RoleCards({ roles, isDeveloper }: { roles: RoleSummary[]; isDeveloper: boolean }) {
    return (
            <div className="grid gap-4">
                {roles.map((role) => (
                    <Card key={role.role} className={role.is_developer ? "border-orange-200 bg-orange-50/30" : ""}>
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <span className="text-2xl">{ROLE_ICONS[role.role] || "👤"}</span>
                                    <div>
                                        <CardTitle className="flex items-center gap-2">
                                            {role.label}
                                            {role.is_developer && (
                                                <Badge variant="outline" className="text-orange-600 border-orange-300">
                                <Lock className="size-3 mr-1" aria-hidden="true" />
                                                    Immutable
                                                </Badge>
                                            )}
                                        </CardTitle>
                                        <CardDescription>
                                            {ROLE_DESCRIPTIONS[role.role] || "Custom role"}
                                        </CardDescription>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <Badge variant="secondary">
                                        {role.permission_count} permissions
                                    </Badge>
                                    {!role.is_developer && (
                                        <Button
                                            render={<Link href={`/settings/team/roles/${role.role}`} />}
                                            variant="outline"
                                            size="sm"
                                        >
                                            {isDeveloper ? "Edit" : "View"}
                                            <ChevronRight className="size-4 ml-1" aria-hidden="true" />
                                        </Button>
                                    )}
                                    {role.is_developer && (
                                        <Button variant="ghost" size="sm" disabled>
                                            All Permissions
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </CardHeader>
                    </Card>
                ))}
            </div>
    )
}
