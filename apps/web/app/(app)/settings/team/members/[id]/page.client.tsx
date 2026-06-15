"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from "@/components/ui/select"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    ChevronLeft, User, Shield, Plus, X, Check, XCircle,
    Loader2, AlertTriangle, Clock, Save
} from "lucide-react"
import {
    useMember,
    useMembers,
    useUpdateMember,
    useRemoveMember,
    useAvailablePermissions,
    useIntakePoolGrants,
    useCreateIntakePoolGrant,
    useRevokeIntakePoolGrant,
} from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { formatDate, formatRelativeTime } from "@/lib/formatters"

function AddOverrideDialog({
    open,
    onOpenChange,
    onAdd,
    existingOverrides,
    effectivePermissions
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    onAdd: (permission: string, type: "grant" | "revoke") => void
    existingOverrides: string[]
    effectivePermissions: string[]
}) {
    const [permission, setPermission] = useState("")
    const [type, setType] = useState<"grant" | "revoke">("grant")
    const { data: allPermissions } = useAvailablePermissions()

    // Filter permissions based on override type:
    // - Grant: show permissions user DOESN'T have (not in effective && not developer_only)
    // - Revoke: show permissions user HAS (in effective)
    // Always exclude already overridden permissions
    const availablePermissions = allPermissions?.filter(p => {
        // Skip if already has an override for this permission
        if (existingOverrides.includes(p.key)) return false
        // Skip developer_only permissions for non-developers
        if (p.developer_only) return false

        if (type === "grant") {
            // Grant: only show permissions they DON'T currently have
            return !effectivePermissions.includes(p.key)
        } else {
            // Revoke: only show permissions they DO currently have
            return effectivePermissions.includes(p.key)
        }
    }) || []

    // Clear selected permission when type changes (since options change)
    const handleTypeChange = (value: string | null) => {
        if (value === "grant" || value === "revoke") {
            setType(value)
        }
        setPermission("") // Reset selection when type changes
    }

    const handleAdd = () => {
        if (permission) {
            onAdd(permission, type)
            onOpenChange(false)
            setPermission("")
        }
    }

    const handlePermissionChange = (value: string | null) => {
        setPermission(value ?? "")
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Add Permission Override</DialogTitle>
                    <DialogDescription>
                        Grant additional permissions or revoke existing ones for this user.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="override-permission">Permission</Label>
                        <Select value={permission} onValueChange={handlePermissionChange}>
                            <SelectTrigger id="override-permission" className="w-full">
                                <SelectValue placeholder="Select permission…">
                                    {(value: string | null) => {
                                        if (!value) return "Select permission…"
                                        const permission = allPermissions?.find(p => p.key === value)
                                        return permission?.label ?? "Unknown permission"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent
                                side="bottom"
                                sideOffset={4}
                                alignItemWithTrigger={false}
                                className="min-w-max max-h-[300px]"
                            >
                                {availablePermissions.map(p => (
                                    <SelectItem key={p.key} value={p.key}>
                                        <div className="whitespace-nowrap">
                                            <span className="font-medium">{p.label}</span>
                                            <span className="text-muted-foreground ml-2">({p.category})</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="override-type">Override Type</Label>
                        <Select value={type} onValueChange={handleTypeChange}>
                            <SelectTrigger id="override-type">
                                <SelectValue>
                                    {(value: string | null) => value === "revoke" ? "Revoke (remove permission)" : "Grant (add permission)"}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="grant">
                                    <div className="flex items-center gap-2">
                                        <Check className="size-4 text-green-600" aria-hidden="true" />
                                        Grant (add permission)
                                    </div>
                                </SelectItem>
                                <SelectItem value="revoke">
                                    <div className="flex items-center gap-2">
                                        <XCircle className="size-4 text-red-600" aria-hidden="true" />
                                        Revoke (remove permission)
                                    </div>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleAdd} disabled={!permission}>Add Override</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default function MemberDetailPage() {
    const params = useParams()
    const { push } = useRouter()
    const rawMemberId = params.id
    const memberId =
        typeof rawMemberId === "string"
            ? rawMemberId
            : Array.isArray(rawMemberId)
              ? rawMemberId[0] ?? ""
              : ""
    const { data: member, isLoading } = useMember(memberId)
    const updateMember = useUpdateMember()
    const removeMember = useRemoveMember()
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const canManageIntakePools = user?.role === "admin" || isDeveloper
    const { data: members } = useMembers()
    const { data: intakePoolGrants } = useIntakePoolGrants(member?.user_id ?? null, {
        enabled: canManageIntakePools,
    })
    const createIntakePoolGrant = useCreateIntakePoolGrant()
    const revokeIntakePoolGrant = useRevokeIntakePoolGrant()

    const [pendingRole, setPendingRole] = useState<string | null>(null)
    const [poolSourceUserId, setPoolSourceUserId] = useState("")
    const [pendingOverrides, setPendingOverrides] = useState<{
        add: { permission: string; override_type: "grant" | "revoke" }[]
        remove: string[]
    }>({ add: [], remove: [] })
    const [showOverrideDialog, setShowOverrideDialog] = useState(false)

    const currentUserId = user?.email  // Use email as identifier since User type may vary
    const isCurrentUser = member?.email === currentUserId
    const hasChanges = pendingRole !== null || pendingOverrides.add.length > 0 || pendingOverrides.remove.length > 0

    const handleRoleChange = (newRole: string | null) => {
        if (newRole === member?.role) {
            setPendingRole(null)
        } else {
            setPendingRole(newRole)
        }
    }

    const handleAddOverride = (permission: string, type: "grant" | "revoke") => {
        setPendingOverrides(prev => ({
            ...prev,
            add: [...prev.add, { permission, override_type: type }],
            remove: prev.remove.filter(p => p !== permission),
        }))
    }

    const handleRemoveOverride = (permission: string) => {
        setPendingOverrides(prev => ({
            ...prev,
            remove: [...prev.remove, permission],
            add: prev.add.filter(o => o.permission !== permission),
        }))
    }

    const handleSave = async () => {
        try {
            await updateMember.mutateAsync({
                memberId,
                data: {
                    ...(pendingRole ? { role: pendingRole } : {}),
                    ...(pendingOverrides.add.length > 0 ? { add_overrides: pendingOverrides.add } : {}),
                    ...(pendingOverrides.remove.length > 0 ? { remove_overrides: pendingOverrides.remove } : {}),
                },
            })
            setPendingRole(null)
            setPendingOverrides({ add: [], remove: [] })
            toast.success("Member updated")
        } catch (error) {
            toast.error("Failed to update member", {
                description: error instanceof Error ? error.message : "Unknown error"
            })
        }
    }

    const handleRemoveMember = async () => {
        if (!confirm(`Remove ${member?.email} from the organization? This cannot be undone.`)) return

        try {
            await removeMember.mutateAsync(memberId)
            toast.success("Member removed")
            push("/settings/team")
        } catch (error) {
            toast.error("Failed to remove member", {
                description: error instanceof Error ? error.message : "Unknown error"
            })
        }
    }

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2 className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    if (!member) return null

    // Combine existing overrides with pending changes
    const displayedOverrides = [
        ...member.overrides.filter(o => !pendingOverrides.remove.includes(o.permission)),
        ...pendingOverrides.add.map(o => ({
            permission: o.permission,
            override_type: o.override_type,
            label: o.permission.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
            category: "Pending",
        })),
    ]

    const currentRole = pendingRole || member.role
    const intakePoolGrantRows = intakePoolGrants ?? []
    const grantedSourceUserIds = new Set(intakePoolGrantRows.map(grant => grant.source_user_id))
    const intakePoolSourceOptions = (members ?? [])
        .filter(candidate =>
            candidate.role === "intake_specialist" &&
            candidate.user_id !== member.user_id &&
            !grantedSourceUserIds.has(candidate.user_id)
        )
        .sort((a, b) => (a.display_name || a.email).localeCompare(b.display_name || b.email))
    const selectedPoolSource = intakePoolSourceOptions.find(option => option.user_id === poolSourceUserId)

    const handleCreateIntakePoolGrant = async () => {
        if (!poolSourceUserId) return

        try {
            await createIntakePoolGrant.mutateAsync({
                source_user_id: poolSourceUserId,
                grantee_user_id: member.user_id,
            })
            setPoolSourceUserId("")
            toast.success("Intake pool access added")
        } catch (error) {
            toast.error("Failed to add intake pool access", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
    }

    const handleRevokeIntakePoolGrant = async (grantId: string) => {
        try {
            await revokeIntakePoolGrant.mutateAsync(grantId)
            toast.success("Intake pool access revoked")
        } catch (error) {
            toast.error("Failed to revoke intake pool access", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
    }

    return (
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-3xl mx-auto">
            <div className="flex items-center justify-between">
                <Button variant="ghost" size="sm" render={<Link href="/settings/team" />}>
                    <ChevronLeft className="size-4 mr-1" aria-hidden="true" />
                    Back to Team
                </Button>
                {hasChanges && (
                    <Button onClick={handleSave} disabled={updateMember.isPending}>
                        {updateMember.isPending ? (
                            <Loader2 className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        ) : (
                            <Save className="size-4 mr-2" aria-hidden="true" />
                        )}
                        Save Changes
                    </Button>
                )}
            </div>

            <Card>
                <CardHeader>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center justify-center size-16 rounded-full bg-muted">
                            <User className="size-8 text-muted-foreground" aria-hidden="true" />
                        </div>
                        <div className="flex-1">
                            <CardTitle className="text-xl flex items-center gap-2">
                                {member.display_name || member.email}
                                {isCurrentUser && (
                                    <Badge variant="outline">You</Badge>
                                )}
                            </CardTitle>
                            <CardDescription>{member.email}</CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span className="text-muted-foreground">Joined</span>
                            <p className="font-medium">
                                {formatDate(member.created_at, { dateStyle: "long" }, "—")}
                            </p>
                        </div>
                        <div>
                            <span className="text-muted-foreground">Last Login</span>
                            <p className="font-medium flex items-center gap-1">
                                {member.last_login_at ? (
                                    <>
                                        <Clock className="size-3" aria-hidden="true" />
                                        {formatRelativeTime(member.last_login_at, "—")}
                                    </>
                                ) : (
                                    "Never"
                                )}
                            </p>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="member-role">Role</Label>
                        <Select
                            value={currentRole}
                            onValueChange={handleRoleChange}
                            disabled={isCurrentUser}
                        >
                            <SelectTrigger id="member-role" className={pendingRole ? "border-yellow-400 bg-yellow-50" : ""}>
                                <SelectValue>
                                    {(value: string | null) => {
                                        const labels: Record<string, string> = {
                                            intake_specialist: "Intake Specialist",
                                            case_manager: "Case Manager",
                                            admin: "Admin",
                                            developer: "Developer",
                                        }
                                        return labels[value ?? ""] ?? "Select role"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="intake_specialist">Intake Specialist</SelectItem>
                                <SelectItem value="case_manager">Case Manager</SelectItem>
                                <SelectItem value="admin">Admin</SelectItem>
                                {isDeveloper && (
                                    <SelectItem value="developer">Developer</SelectItem>
                                )}
                            </SelectContent>
                        </Select>
                        {isCurrentUser && (
                            <p className="text-xs text-muted-foreground">
                                You cannot change your own role.
                            </p>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                <Shield className="size-5" aria-hidden="true" />
                                Permission Overrides
                            </CardTitle>
                            <CardDescription>
                                Grant or revoke individual permissions beyond the role defaults.
                            </CardDescription>
                        </div>
                        {!isCurrentUser && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setShowOverrideDialog(true)}
                            >
                                <Plus className="size-4 mr-1" aria-hidden="true" />
                                Add Override
                            </Button>
                        )}
                    </div>
                </CardHeader>
                <CardContent>
                    {displayedOverrides.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                            No permission overrides. This user has the standard permissions for their role.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {displayedOverrides.map((override) => (
                                <div
                                    key={override.permission}
                                    className={`flex items-center justify-between p-3 rounded-lg ${override.category === "Pending"
                                        ? "bg-yellow-50 border border-yellow-200"
                                        : "bg-muted/50"
                                        }`}
                                >
                                    <div className="flex items-center gap-3">
                                        {override.override_type === "grant" ? (
                                            <Check className="size-5 text-green-600" aria-hidden="true" />
                                        ) : (
                                            <XCircle className="size-5 text-red-600" aria-hidden="true" />
                                        )}
                                        <div>
                                            <p className="font-medium">{override.label}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {override.override_type === "grant" ? "Granted" : "Revoked"} • {override.category}
                                            </p>
                                        </div>
                                    </div>
                                    {!isCurrentUser && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleRemoveOverride(override.permission)}
                                            aria-label={`Remove ${override.label} override`}
                                        >
                                            <X className="size-4" aria-hidden="true" />
                                        </Button>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {canManageIntakePools && currentRole === "intake_specialist" && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Shield className="size-5" aria-hidden="true" />
                            Intake Pool Access
                        </CardTitle>
                        <CardDescription>
                            Allow this intake specialist to work another intake specialist&apos;s owned cases.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                            <div className="space-y-2">
                                <Label htmlFor="intake-pool-source">Source intake pool</Label>
                                <Select
                                    value={poolSourceUserId || "none"}
                                    onValueChange={(value) => setPoolSourceUserId(value === "none" ? "" : value ?? "")}
                                >
                                    <SelectTrigger id="intake-pool-source">
                                        <SelectValue placeholder="Select intake pool">
                                            {(value: string | null) => {
                                                if (!value || value === "none") return "Select intake pool"
                                                return selectedPoolSource?.display_name || selectedPoolSource?.email || "Unknown intake"
                                            }}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">Select intake pool</SelectItem>
                                        {intakePoolSourceOptions.map(source => (
                                            <SelectItem key={source.user_id} value={source.user_id}>
                                                {source.display_name || source.email}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="flex items-end">
                                <Button
                                    type="button"
                                    onClick={handleCreateIntakePoolGrant}
                                    disabled={!poolSourceUserId || createIntakePoolGrant.isPending}
                                >
                                    {createIntakePoolGrant.isPending ? (
                                        <Loader2 className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    ) : (
                                        <Plus className="size-4 mr-2" aria-hidden="true" />
                                    )}
                                    Add Access
                                </Button>
                            </div>
                        </div>

                        {intakePoolGrantRows.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-2">
                                No intake pool access grants.
                            </p>
                        ) : (
                            <div className="space-y-2">
                                {intakePoolGrantRows.map(grant => (
                                    <div
                                        key={grant.id}
                                        className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 p-3"
                                    >
                                        <div>
                                            <p className="font-medium">
                                                {grant.source_user_name || grant.source_user_email}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {grant.source_user_email}
                                            </p>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleRevokeIntakePoolGrant(grant.id)}
                                            disabled={revokeIntakePoolGrant.isPending}
                                            aria-label={`Revoke ${grant.source_user_name || grant.source_user_email} access`}
                                        >
                                            <X className="size-4" aria-hidden="true" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {!isCurrentUser && (
                <Card className="border-destructive/50">
                    <CardHeader>
                        <CardTitle className="text-destructive flex items-center gap-2">
                            <AlertTriangle className="size-5" aria-hidden="true" />
                            Danger Zone
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="font-medium">Remove from organization</p>
                                <p className="text-sm text-muted-foreground">
                                    This will revoke all access and delete permission overrides.
                                </p>
                            </div>
                            <Button
                                variant="destructive"
                                onClick={handleRemoveMember}
                                disabled={removeMember.isPending}
                            >
                                {removeMember.isPending && (
                                    <Loader2 className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                )}
                                Remove Member
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            <AddOverrideDialog
                open={showOverrideDialog}
                onOpenChange={setShowOverrideDialog}
                onAdd={handleAddOverride}
                existingOverrides={displayedOverrides.map(o => o.permission)}
                effectivePermissions={member?.effective_permissions || []}
            />
        </div>
    )
}
