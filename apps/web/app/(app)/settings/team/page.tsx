"use client"

import { useState } from "react"
import Link from "@/components/app-link"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { ValidatedField } from "@/components/ui/field"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createSelectLabelGetter } from "@/lib/select-labels"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { useFormValidation } from "@/lib/forms/use-form-validation"
import { EMAIL_INVALID_MESSAGE, validateEmail } from "@/lib/forms/validators"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Loader2, UserPlus, Mail, RotateCcw, X,
    Users, Shield, Settings2, UserCog
} from "lucide-react"
import { useInvites, useCreateInvite, useResendInvite, useRevokeInvite } from "@/lib/hooks/use-invites"
import { useMembers, useRemoveMember, useBulkUpdateRoles } from "@/lib/hooks/use-permissions"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import { Checkbox } from "@/components/ui/checkbox"
import { formatRelativeTime } from "@/lib/formatters"
import { SettingsPageGate } from "../settings-page-gate"

const ROLE_LABELS: Record<string, string> = {
    intake_specialist: "Intake Specialist",
    case_manager: "Case Manager",
    admin: "Admin",
    developer: "Developer",
}

const ROLE_COLORS: Record<string, string> = {
    intake_specialist: "bg-blue-100 text-blue-800",
    case_manager: "bg-green-100 text-green-800",
    admin: "bg-purple-100 text-purple-800",
    developer: "bg-orange-100 text-orange-800",
}

const INVITE_ROLE_OPTIONS = ["intake_specialist", "case_manager", "admin"] as const
type InviteRole = (typeof INVITE_ROLE_OPTIONS)[number]
const ACTIONABLE_INVITE_STATUSES = new Set(["pending", "expired"])

const getInviteRoleLabel = createSelectLabelGetter(ROLE_LABELS, {
    emptyLabel: "Select role",
    unknownLabel: "Unknown role",
})

type PendingRemoval = { id: string; email: string }

type InviteFormValues = {
    email: string
    role: InviteRole | ""
}

function validateInviteForm(values: InviteFormValues) {
    return {
        email: validateEmail(values.email, { requiredMessage: "Enter an email address." }),
        role: values.role ? undefined : "Select a role.",
    }
}

function InviteTeamModal({ onClose }: { onClose: () => void }) {
    const [values, setValues] = useState<InviteFormValues>({ email: "", role: INVITE_ROLE_OPTIONS[0] })
    const createInvite = useCreateInvite()
    const form = useFormValidation({ values, validate: validateInviteForm })

    const handleSubmit = form.handleSubmit(async ({ email, role }) => {
        if (!role) return
        const trimmedEmail = email.trim()
        try {
            await createInvite.mutateAsync({ email: trimmedEmail, role })
            toast.success(`Invited ${trimmedEmail} as ${ROLE_LABELS[role] || role}`)
            setValues({ email: "", role: INVITE_ROLE_OPTIONS[0] })
            form.reset()
            onClose()
        } catch (error) {
            const formError = form.applyApiError(error, {
                fields: ["email", "role"],
                messages: { email: EMAIL_INVALID_MESSAGE },
                fallback: "Couldn't send the invitation. Try again.",
            })
            if (formError) toast.error(formError)
        }
    })

    return (
        <DialogContent>
            <form onSubmit={handleSubmit} noValidate>
                <DialogHeader>
                    <DialogTitle>Invite Team Member</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <ValidatedField label="Email address" id="email" error={form.errorFor("email")}>
                        {(control) => (
                            <Input
                                {...control}
                                name="inviteEmail"
                                type="email"
                                placeholder="colleague@example.com"
                                value={values.email}
                                onChange={(e) => setValues((current) => ({ ...current, email: e.target.value }))}
                                onBlur={() => form.touch("email")}
                                autoComplete="email"
                                spellCheck={false}
                            />
                        )}
                    </ValidatedField>

                    <ValidatedField label="Role" id="role" error={form.errorFor("role")}>
                        {(control) => (
                            <Select
                                value={values.role}
                                onValueChange={(v) =>
                                    v && setValues((current) => ({ ...current, role: v as InviteRole }))
                                }
                            >
                                <SelectTrigger {...control} className="w-full">
                                    <SelectValue placeholder="Select role">{getInviteRoleLabel}</SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {INVITE_ROLE_OPTIONS.map((roleOption) => (
                                        <SelectItem key={roleOption} value={roleOption}>
                                            {ROLE_LABELS[roleOption]}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </ValidatedField>
                </div>

                <DialogFooter>
                    <Button type="button" variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button type="submit" disabled={createInvite.isPending || !form.isValid}>
                        {createInvite.isPending && (
                            <Loader2 className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        )}
                        Send Invitation
                    </Button>
                </DialogFooter>
            </form>
        </DialogContent>
    )
}

function MembersTab() {
    const { data: members, isLoading, isError, error, refetch, isFetching } = useMembers()
    const removeMember = useRemoveMember()
    const bulkUpdate = useBulkUpdateRoles()
    const { user } = useAuth()

    // Selection state for bulk operations
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
    const [showBulkDialog, setShowBulkDialog] = useState(false)
    const [bulkRole, setBulkRole] = useState("case_manager")
    const [pendingRemoval, setPendingRemoval] = useState<PendingRemoval | null>(null)
    const [removalOpen, setRemovalOpen] = useState(false)

    const handleConfirmRemove = async () => {
        if (!pendingRemoval) return
        await removeMember.mutateAsync(pendingRemoval.id)
        setSelectedIds((current) => {
            if (!current.has(pendingRemoval.id)) return current
            const next = new Set(current)
            next.delete(pendingRemoval.id)
            return next
        })
        toast.success("Member removed")
    }

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev)
            if (next.has(id)) {
                next.delete(id)
            } else {
                next.add(id)
            }
            return next
        })
    }

    const toggleSelectAll = () => {
        if (!members) return
        const selectableIds: string[] = []

        for (const member of members) {
            if (member.user_id === user?.user_id || member.role === "developer") continue
            selectableIds.push(member.id)
        }

        if (selectedIds.size === selectableIds.length) {
            setSelectedIds(new Set())
        } else {
            setSelectedIds(new Set(selectableIds))
        }
    }

    const handleBulkAssign = async () => {
        if (selectedIds.size === 0) return

        try {
            const result = await bulkUpdate.mutateAsync({
                memberIds: Array.from(selectedIds),
                role: bulkRole,
            })
            toast.success(`${result.success} member(s) updated${result.failed > 0 ? `, ${result.failed} failed` : ""}`)
            setSelectedIds(new Set())
            setShowBulkDialog(false)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't update roles. Try again.")
            if (message) toast.error(message)
        }
    }

    if (isLoading) {
        return (
            <div className="flex justify-center py-8">
                <Loader2 className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    if (isError) {
        return (
            <QueryErrorState
                error={error}
                onRetry={() => void refetch()}
                isRetrying={isFetching}
                title="Couldn't load team members"
                className="min-h-0 py-10"
            />
        )
    }

    if (!members?.length) {
        return <EmptyState icon={Users} title="No team members" />
    }

    const selectableMembers = members.filter(m => m.user_id !== user?.user_id && m.role !== "developer")
    const allSelected = selectableMembers.length > 0 && selectedIds.size === selectableMembers.length

    return (
        <div>
            {/* Bulk Actions Bar */}
            {selectedIds.size > 0 && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
                    <span className="text-sm text-blue-800">
                        {selectedIds.size} member{selectedIds.size !== 1 ? "s" : ""} selected
                    </span>
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedIds(new Set())}
                        >
                            Clear Selection
                        </Button>
                        <Dialog open={showBulkDialog} onOpenChange={setShowBulkDialog}>
                            <DialogTrigger render={
                                <Button size="sm">
                                    <UserCog className="size-4 mr-2" aria-hidden="true" />
                                    Assign Role
                                </Button>
                            } />
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Bulk Assign Role</DialogTitle>
                                    <DialogDescription>
                                        Assign the same role to {selectedIds.size} selected member{selectedIds.size !== 1 ? "s" : ""}.
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="py-4 space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="bulk-role">New Role</Label>
                                        <Select value={bulkRole} onValueChange={(v) => v && setBulkRole(v)}>
                                            <SelectTrigger id="bulk-role">
                                                <SelectValue placeholder="Select role">{getInviteRoleLabel}</SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {INVITE_ROLE_OPTIONS.map((roleOption) => (
                                                    <SelectItem key={roleOption} value={roleOption}>
                                                        {ROLE_LABELS[roleOption]}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setShowBulkDialog(false)}>
                                        Cancel
                                    </Button>
                                    <Button onClick={handleBulkAssign} disabled={bulkUpdate.isPending}>
                                        {bulkUpdate.isPending && (
                                            <Loader2 className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        )}
                                        Apply to {selectedIds.size} Member{selectedIds.size !== 1 ? "s" : ""}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>
            )}

            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-12 text-center">
                            <Checkbox
                                checked={allSelected}
                                onCheckedChange={toggleSelectAll}
                                aria-label="Select all"
                            />
                        </TableHead>
                        <TableHead className="text-center">Name</TableHead>
                        <TableHead className="text-center">Email</TableHead>
                        <TableHead className="text-center">Role</TableHead>
                        <TableHead className="text-center">Last Login</TableHead>
                        <TableHead className="text-center">Actions</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {members.map((member) => {
                        const isSelectable = member.user_id !== user?.user_id && member.role !== "developer"
                        const isSelected = selectedIds.has(member.id)

                        return (
                            <TableRow key={member.id} className={isSelected ? "bg-blue-50" : ""}>
                                <TableCell className="text-center">
                                    <Checkbox
                                        checked={isSelected}
                                        onCheckedChange={() => toggleSelect(member.id)}
                                        disabled={!isSelectable}
                                        aria-label={`Select ${member.email}`}
                                    />
                                </TableCell>
                                <TableCell className="font-medium text-center">
                                    {member.display_name || "—"}
                                </TableCell>
                                <TableCell className="text-center">{member.email}</TableCell>
                                <TableCell className="text-center">
                                    <Badge className={ROLE_COLORS[member.role] || "bg-gray-100"}>
                                        {ROLE_LABELS[member.role] || member.role}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-muted-foreground text-center">
                                    {member.last_login_at
                                        ? formatRelativeTime(member.last_login_at, "Never")
                                        : "Never"}
                                </TableCell>
                                <TableCell className="text-center">
                                    <div className="grid grid-cols-[auto_3.5rem] items-center justify-center gap-2">
                                        <Button
                                            render={<Link href={`/settings/team/members/${member.id}`} />}
                                            variant="ghost"
                                            size="sm"
                                        >
                                            <Settings2 className="size-4 mr-1" aria-hidden="true" />
                                            Manage
                                        </Button>
                                        <div className="flex w-14 justify-center">
                                            {member.user_id !== user?.user_id ? (
                                                <Button
                                                    variant="destructive-ghost"
                                                    size="sm"
                                                    onClick={() => {
                                                        setPendingRemoval({ id: member.id, email: member.email })
                                                        setRemovalOpen(true)
                                                    }}
                                                    className="text-muted-foreground"
                                                    aria-label={`Remove ${member.email}`}
                                                >
                                                    <X className="size-4" aria-hidden="true" />
                                                </Button>
                                            ) : (
                                                <Badge variant="outline" className="text-xs">You</Badge>
                                            )}
                                        </div>
                                    </div>
                                </TableCell>
                            </TableRow>
                        )
                    })}
                </TableBody>
            </Table>

            <ConfirmDialog
                open={removalOpen}
                onOpenChange={setRemovalOpen}
                title={`Remove ${pendingRemoval?.email ?? "member"}?`}
                description="They lose access to the organization. This cannot be undone."
                confirmLabel="Remove member"
                errorFallback="Couldn't remove this member. Try again."
                onConfirm={handleConfirmRemove}
            />
        </div>
    )
}

function InvitationsTab() {
    const { data, isLoading, isError, error, refetch, isFetching } = useInvites()
    const resendInvite = useResendInvite()
    const revokeInvite = useRevokeInvite()
    const [pendingRevoke, setPendingRevoke] = useState<PendingRemoval | null>(null)
    const [revokeOpen, setRevokeOpen] = useState(false)

    const handleResend = async (inviteId: string) => {
        try {
            await resendInvite.mutateAsync(inviteId)
            toast.success("Invitation resent")
        } catch (resendError) {
            const message = getActionErrorMessage(resendError, "Couldn't resend the invitation. Try again.")
            if (message) toast.error(message)
        }
    }

    const handleConfirmRevoke = async () => {
        if (!pendingRevoke) return
        await revokeInvite.mutateAsync(pendingRevoke.id)
        toast.success("Invitation revoked")
    }

    const actionableInvites = data?.invites.filter((inv) => ACTIONABLE_INVITE_STATUSES.has(inv.status)) || []

    if (isLoading) {
        return (
            <div className="flex justify-center py-8">
                <Loader2 className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    if (isError) {
        return (
            <QueryErrorState
                error={error}
                onRetry={() => void refetch()}
                isRetrying={isFetching}
                title="Couldn't load invitations"
                className="min-h-0 py-10"
            />
        )
    }

    if (actionableInvites.length === 0) {
        return <EmptyState icon={Mail} title="No pending invitations" />
    }

    return (
        <>
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="text-center">Email</TableHead>
                    <TableHead className="text-center">Role</TableHead>
                    <TableHead className="text-center">Expires</TableHead>
                    <TableHead className="text-center">Resends</TableHead>
                    <TableHead className="text-center">Actions</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {actionableInvites.map((invite) => (
                    <TableRow key={invite.id}>
                        <TableCell className="font-medium text-center">{invite.email}</TableCell>
                        <TableCell className="text-center">
                            <Badge className={ROLE_COLORS[invite.role] || "bg-gray-100"}>
                                {ROLE_LABELS[invite.role] || invite.role}
                            </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-center">
                            {invite.expires_at
                                ? formatRelativeTime(invite.expires_at, "Never")
                                : "Never"}
                        </TableCell>
                        <TableCell className="text-center">{invite.resend_count}/3</TableCell>
                        <TableCell className="text-center">
                            <div className="flex items-center justify-center gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleResend(invite.id)}
                                    disabled={!invite.can_resend || resendInvite.isPending}
                                    aria-label={`Resend invitation to ${invite.email}`}
                                >
                                    <RotateCcw className="size-4" aria-hidden="true" />
                                </Button>
                                <Button
                                    variant="destructive-ghost"
                                    size="sm"
                                    onClick={() => {
                                        setPendingRevoke({ id: invite.id, email: invite.email })
                                        setRevokeOpen(true)
                                    }}
                                    className="text-muted-foreground"
                                    aria-label={`Revoke invitation for ${invite.email}`}
                                >
                                    <X className="size-4" aria-hidden="true" />
                                </Button>
                            </div>
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>

        <ConfirmDialog
            open={revokeOpen}
            onOpenChange={setRevokeOpen}
            title={`Revoke the invitation for ${pendingRevoke?.email ?? "this person"}?`}
            description="The invitation link stops working."
            confirmLabel="Revoke invitation"
            errorFallback="Couldn't revoke the invitation. Try again."
            onConfirm={handleConfirmRevoke}
        />
        </>
    )
}

export default function TeamSettingsPage() {
    return (
        <SettingsPageGate
            title="Team"
            permission="manage_team"
            deniedDescription="Team settings need the Manage team permission. Ask an admin to update your role."
        >
            <TeamSettingsContent />
        </SettingsPageGate>
    )
}

function TeamSettingsContent() {
    const [showInviteModal, setShowInviteModal] = useState(false)
    const { data: inviteData } = useInvites()
    const { data: members } = useMembers()

    const actionableInviteCount = inviteData?.invites.filter((inv) => ACTIONABLE_INVITE_STATUSES.has(inv.status)).length || 0
    const memberCount = members?.length || 0

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader
                title="Team"
                count={members ? memberCount : null}
                countLabel="members"
                actions={
                    <>
                        <Button
                            render={<Link href="/settings/team/roles" />}
                            variant="outline"
                            className="flex-1 sm:flex-none"
                        >
                            <Shield className="size-4 mr-2" aria-hidden="true" />
                            Role Permissions
                        </Button>
                        <Dialog open={showInviteModal} onOpenChange={setShowInviteModal}>
                            <DialogTrigger render={
                                <Button className="flex-1 sm:flex-none">
                                    <UserPlus className="size-4 mr-2" aria-hidden="true" />
                                    Invite Member
                                </Button>
                            } />
                            <InviteTeamModal onClose={() => setShowInviteModal(false)} />
                        </Dialog>
                    </>
                }
            />

            <div className="p-6">
            <Card>
                <CardContent>
                    <Tabs defaultValue="members">
                        <TabsList className="mb-4">
                            <TabsTrigger value="members">
                                <Users className="size-4 mr-1" aria-hidden="true" />
                                Members ({memberCount})
                            </TabsTrigger>
                            <TabsTrigger value="invitations">
                                <Mail className="size-4 mr-1" aria-hidden="true" />
                                Invitations ({actionableInviteCount})
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="members">
                            <MembersTab />
                        </TabsContent>

                        <TabsContent value="invitations">
                            <InvitationsTab />
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>
            </div>
        </div>
    )
}
