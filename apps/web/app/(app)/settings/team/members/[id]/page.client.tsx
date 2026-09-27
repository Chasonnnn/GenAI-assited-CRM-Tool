"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { SaveBar } from "@/components/ui/save-bar"
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
    User, Shield, Plus, X, Check, XCircle,
    Loader2, AlertTriangle, Clock
} from "lucide-react"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import {
    useMember,
    useUpdateMember,
    useRemoveMember,
    useAvailablePermissions,
} from "@/lib/hooks/use-permissions"
import type { MemberDetail } from "@/lib/api/permissions"
import { useAuth } from "@/lib/auth-context"
import { toast } from "@/components/ui/toast"
import { formatDate, formatRelativeTime } from "@/lib/formatters"
import { SettingsPageGate } from "../../../settings-page-gate"

type DisplayedOverride = MemberDetail["overrides"][number]

const ROLE_LABELS: Record<string, string> = {
    intake_specialist: "Intake Specialist",
    case_manager: "Case Manager",
    admin: "Admin",
    developer: "Developer",
}

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
    const existingOverrideKeys = new Set(existingOverrides)
    const effectivePermissionKeys = new Set(effectivePermissions)

    // Filter permissions based on override type:
    // - Grant: show permissions user DOESN'T have (not in effective && not developer_only)
    // - Revoke: show permissions user HAS (in effective)
    // Always exclude already overridden permissions
    const availablePermissions = allPermissions?.filter(p => {
        // Skip if already has an override for this permission
        if (existingOverrideKeys.has(p.key)) return false
        // Skip developer_only permissions for non-developers
        if (p.developer_only) return false

        if (type === "grant") {
            // Grant: only show permissions they DON'T currently have
            return !effectivePermissionKeys.has(p.key)
        } else {
            // Revoke: only show permissions they DO currently have
            return effectivePermissionKeys.has(p.key)
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
                                <SelectItem value="grant">Grant (add permission)</SelectItem>
                                <SelectItem value="revoke">Revoke (remove permission)</SelectItem>
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

const TEAM_BACK_LINK = { href: "/settings/team", label: "Back to Team" }

export default function MemberDetailPage() {
    return (
        <SettingsPageGate
            title="Team Member"
            permission="manage_team"
            deniedDescription="Team settings need the Manage team permission. Ask an admin to update your role."
            back={TEAM_BACK_LINK}
        >
            <MemberDetailContent />
        </SettingsPageGate>
    )
}

function MemberDetailContent() {
    const params = useParams()
    const { push } = useRouter()
    const rawMemberId = params.id
    const memberId =
        typeof rawMemberId === "string"
            ? rawMemberId
            : Array.isArray(rawMemberId)
              ? rawMemberId[0] ?? ""
              : ""
    const { data: member, isLoading, isError, error, refetch, isFetching } = useMember(memberId)
    const updateMember = useUpdateMember()
    const removeMember = useRemoveMember()
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const [pendingRole, setPendingRole] = useState<string | null>(null)
    const [pendingOverrides, setPendingOverrides] = useState<{
        add: { permission: string; override_type: "grant" | "revoke" }[]
        remove: string[]
    }>({ add: [], remove: [] })
    const [showOverrideDialog, setShowOverrideDialog] = useState(false)

    const currentUserId = user?.email  // Use email as identifier since User type may vary
    const isCurrentUser = member?.email === currentUserId
    const changeCount = (pendingRole !== null ? 1 : 0) + pendingOverrides.add.length + pendingOverrides.remove.length
    const hasChanges = changeCount > 0

    const handleDiscard = () => {
        setPendingRole(null)
        setPendingOverrides({ add: [], remove: [] })
    }

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
        } catch (saveError) {
            const message = getActionErrorMessage(saveError, "Couldn't update this member. Try again.")
            if (message) toast.error(message)
        }
    }

    // ConfirmDialog keeps itself open while this runs and shows a rejection inline.
    const handleRemoveMember = async () => {
        await removeMember.mutateAsync(memberId)
        toast.success("Member removed")
        push("/settings/team")
    }

    if (isLoading || isError || !member) {
        return (
            <div className="flex min-h-screen flex-col">
                <PageHeader title="Team Member" back={TEAM_BACK_LINK} />
                {isLoading ? (
                    <div className="flex items-center justify-center p-12" role="status" aria-label="Loading">
                        <Loader2 className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : (
                    <QueryErrorState
                        error={error}
                        onRetry={() => void refetch()}
                        isRetrying={isFetching}
                        title="Couldn't load this member"
                        notFound={{
                            title: "Member not found",
                            backHref: TEAM_BACK_LINK.href,
                            backLabel: TEAM_BACK_LINK.label,
                        }}
                        headingLevel={2}
                    />
                )}
            </div>
        )
    }

    // Combine existing overrides with pending changes
    const pendingOverrideRemovals = new Set(pendingOverrides.remove)
    const displayedOverrides = [
        ...member.overrides.filter(o => !pendingOverrideRemovals.has(o.permission)),
        ...pendingOverrides.add.map(o => ({
            permission: o.permission,
            override_type: o.override_type,
            label: o.permission.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
            category: "Pending",
        })),
    ]

    const currentRole = pendingRole || member.role

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader title={member.display_name || member.email} back={TEAM_BACK_LINK} />

            <div className="flex max-w-3xl flex-1 flex-col gap-6 p-6">
            <MemberProfileCard
                member={member}
                isCurrentUser={isCurrentUser}
                currentRole={currentRole}
                pendingRole={pendingRole}
                isDeveloper={isDeveloper}
                onRoleChange={handleRoleChange}
            />

            <PermissionOverridesCard
                displayedOverrides={displayedOverrides}
                isCurrentUser={isCurrentUser}
                onAddOverride={() => setShowOverrideDialog(true)}
                onRemoveOverride={handleRemoveOverride}
            />

            {!isCurrentUser && (
                <DangerZoneCard
                    email={member.email}
                    onRemoveMember={handleRemoveMember}
                />
            )}

            <AddOverrideDialog
                open={showOverrideDialog}
                onOpenChange={setShowOverrideDialog}
                onAdd={handleAddOverride}
                existingOverrides={getOverridePermissions(displayedOverrides)}
                effectivePermissions={member?.effective_permissions || []}
            />
            </div>

            <SaveBar
                dirty={hasChanges}
                changeCount={changeCount}
                saving={updateMember.isPending}
                onSave={() => void handleSave()}
                onDiscard={handleDiscard}
            />
        </div>
    )
}

function getOverridePermissions(overrides: DisplayedOverride[]) {
    return overrides.map(o => o.permission)
}

function MemberProfileCard({
    member,
    isCurrentUser,
    currentRole,
    pendingRole,
    isDeveloper,
    onRoleChange,
}: {
    member: MemberDetail
    isCurrentUser: boolean
    currentRole: string
    pendingRole: string | null
    isDeveloper: boolean
    onRoleChange: (newRole: string | null) => void
}) {
    return (
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
                        onValueChange={onRoleChange}
                        disabled={isCurrentUser}
                    >
                        <SelectTrigger id="member-role" className={pendingRole ? "border-warning bg-warning/10" : ""}>
                            <SelectValue>
                                {(value: string | null) => ROLE_LABELS[value ?? ""] ?? "Select role"}
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
    )
}

function PermissionOverridesCard({
    displayedOverrides,
    isCurrentUser,
    onAddOverride,
    onRemoveOverride,
}: {
    displayedOverrides: DisplayedOverride[]
    isCurrentUser: boolean
    onAddOverride: () => void
    onRemoveOverride: (permission: string) => void
}) {
    return (
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
                            onClick={onAddOverride}
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
                                    ? "bg-warning/10 border border-warning/40"
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
                                        onClick={() => onRemoveOverride(override.permission)}
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
    )
}

function DangerZoneCard({
    email,
    onRemoveMember,
}: {
    email: string
    onRemoveMember: () => Promise<void>
}) {
    return (
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
                    <ConfirmDialog
                        trigger={<Button variant="destructive">Remove Member</Button>}
                        title={`Remove ${email}?`}
                        description="They lose access to the organization. This cannot be undone."
                        confirmLabel="Remove member"
                        errorFallback="Couldn't remove this member. Try again."
                        onConfirm={onRemoveMember}
                    />
                </div>
            </CardContent>
        </Card>
    )
}
