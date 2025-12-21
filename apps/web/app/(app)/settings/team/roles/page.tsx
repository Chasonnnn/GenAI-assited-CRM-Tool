"use client"

import Link from "next/link"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ChevronLeft, ChevronRight, Shield, Lock, Loader2 } from "lucide-react"
import { useRoles } from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"

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

export default function RolePermissionsPage() {
    const { data: roles, isLoading } = useRoles()
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-4xl mx-auto">
            <div className="flex items-center gap-4">
                <Link href="/settings/team">
                    <Button variant="ghost" size="sm">
                        <ChevronLeft className="size-4 mr-1" />
                        Back to Team
                    </Button>
                </Link>
            </div>

            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Shield className="size-6" />
                    Role Permissions
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Configure default permissions for each role in your organization.
                    {!isDeveloper && " Only Developers can modify role defaults."}
                </p>
            </div>

            <div className="grid gap-4">
                {roles?.map((role) => (
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
                                                    <Lock className="size-3 mr-1" />
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
                                        <Link href={`/settings/team/roles/${role.role}`}>
                                            <Button variant="outline" size="sm">
                                                {isDeveloper ? "Edit" : "View"}
                                                <ChevronRight className="size-4 ml-1" />
                                            </Button>
                                        </Link>
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

            {!isDeveloper && (
                <div className="bg-muted/50 rounded-lg p-4 text-sm text-muted-foreground">
                    <p>
                        <strong>Note:</strong> Role permission defaults can only be modified by Developers.
                        Contact your administrator to request changes.
                    </p>
                </div>
            )}
        </div>
    )
}
