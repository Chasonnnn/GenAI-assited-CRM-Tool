"use client"

import { useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Loader2, UserPlus, Mail, RotateCcw, X, Clock, Check, XCircle,
    Users, Shield, ChevronRight, Settings2, UserCog
} from "lucide-react"
import { useInvites, useCreateInvite, useResendInvite, useRevokeInvite } from "@/lib/hooks/use-invites"
import { useMembers, useRemoveMember, useBulkUpdateRoles } from "@/lib/hooks/use-permissions"
import { toast } from "sonner"
import { formatDistanceToNow } from "date-fns"
import { useAuth } from "@/lib/auth-context"
import { Checkbox } from "@/components/ui/checkbox"

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

function getStatusBadge(status: string) {
    switch (status) {
        case "pending":
            return (
                <Badge variant="outline" className="text-yellow-600 border-yellow-300 bg-yellow-50">
                    <Clock className="size-3 mr-1" />
                    Pending
                </Badge>
            )
        case "accepted":
            return (
                <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50">
                    <Check className="size-3 mr-1" />
                    Accepted
                </Badge>
            )
        case "expired":
            return (
                <Badge variant="outline" className="text-gray-600 border-gray-300 bg-gray-50">
                    <Clock className="size-3 mr-1" />
                    Expired
                </Badge>
            )
        case "revoked":
            return (
                <Badge variant="outline" className="text-red-600 border-red-300 bg-red-50">
                    <XCircle className="size-3 mr-1" />
                    Revoked
                </Badge>
            )
        default:
            return <Badge variant="outline">{status}</Badge>
    }
}

function InviteTeamModal({ onClose }: { onClose: () => void }) {
    const [email, setEmail] = useState("")
    const [role, setRole] = useState("intake_specialist")
    const createInvite = useCreateInvite()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        try {
            await createInvite.mutateAsync({ email, role })
            toast.success(`Invited ${email} as ${ROLE_LABELS[role] || role}`)
            onClose()
        } catch (error) {
            toast.error("Failed to send invitation", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
    }

    return (
        <DialogContent>
            <form onSubmit={handleSubmit}>
                <DialogHeader>
                    <DialogTitle>Invite Team Member</DialogTitle>
                    <DialogDescription>
                        Send an invitation email to add someone to your organization.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="email">Email address</Label>
                        <Input
                            id="email"
                            type="email"
                            placeholder="colleague@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="role">Role</Label>
                        <Select value={role} onValueChange={(v) => v && setRole(v)}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="intake_specialist">Intake Specialist</SelectItem>
                                <SelectItem value="case_manager">Case Manager</SelectItem>
                                <SelectItem value="admin">Admin</SelectItem>
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            Role permissions can be customized after invitation is accepted.
                        </p>
                    </div>
                </div>

                <DialogFooter>
                    <Button type="button" variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button type="submit" disabled={createInvite.isPending}>
                        {createInvite.isPending && <Loader2 className="size-4 mr-2 animate-spin" />}
                        Send Invitation
                    </Button>
                </DialogFooter>
            </form>
        </DialogContent>
    )
}

function MembersTab() {
    const { data: members, isLoading } = useMembers()
    const removeMember = useRemoveMember()
    const bulkUpdate = useBulkUpdateRoles()
    const { user } = useAuth()

    // Selection state for bulk operations
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
    const [showBulkDialog, setShowBulkDialog] = useState(false)
    const [bulkRole, setBulkRole] = useState("case_manager")

    const handleRemove = async (memberId: string, email: string) => {
        if (!confirm(`Remove ${email} from the organization? This cannot be undone.`)) return

        try {
            await removeMember.mutateAsync(memberId)
            toast.success("Member removed")
        } catch (error) {
            toast.error("Failed to remove member", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
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
        const selectableIds = members
            .filter(m => m.user_id !== user?.user_id && m.role !== "developer")
            .map(m => m.id)

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
            toast.error("Failed to update roles", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
    }

    if (isLoading) {
        return (
            <div className="flex justify-center py-8">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!members?.length) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                No team members yet
            </div>
        )
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
                                    <UserCog className="size-4 mr-2" />
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
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="intake_specialist">Intake Specialist</SelectItem>
                                                <SelectItem value="case_manager">Case Manager</SelectItem>
                                                <SelectItem value="admin">Admin</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setShowBulkDialog(false)}>
                                        Cancel
                                    </Button>
                                    <Button onClick={handleBulkAssign} disabled={bulkUpdate.isPending}>
                                        {bulkUpdate.isPending && <Loader2 className="size-4 mr-2 animate-spin" />}
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
                        <TableHead className="w-12">
                            <Checkbox
                                checked={allSelected}
                                onCheckedChange={toggleSelectAll}
                                aria-label="Select all"
                            />
                        </TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Last Login</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {members.map((member) => {
                        const isSelectable = member.user_id !== user?.user_id && member.role !== "developer"
                        const isSelected = selectedIds.has(member.id)

                        return (
                            <TableRow key={member.id} className={isSelected ? "bg-blue-50" : ""}>
                                <TableCell>
                                    <Checkbox
                                        checked={isSelected}
                                        onCheckedChange={() => toggleSelect(member.id)}
                                        disabled={!isSelectable}
                                        aria-label={`Select ${member.email}`}
                                    />
                                </TableCell>
                                <TableCell className="font-medium">
                                    {member.display_name || "—"}
                                    {member.user_id === user?.user_id && (
                                        <Badge variant="outline" className="ml-2 text-xs">You</Badge>
                                    )}
                                </TableCell>
                                <TableCell>{member.email}</TableCell>
                                <TableCell>
                                    <Badge className={ROLE_COLORS[member.role] || "bg-gray-100"}>
                                        {ROLE_LABELS[member.role] || member.role}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-muted-foreground">
                                    {member.last_login_at
                                        ? formatDistanceToNow(new Date(member.last_login_at), { addSuffix: true })
                                        : "Never"}
                                </TableCell>
                                <TableCell className="text-right space-x-2">
                                    <Link href={`/settings/team/members/${member.id}`}>
                                        <Button variant="ghost" size="sm">
                                            <Settings2 className="size-4 mr-1" />
                                            Manage
                                        </Button>
                                    </Link>
                                    {member.user_id !== user?.user_id && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleRemove(member.id, member.email)}
                                            disabled={removeMember.isPending}
                                            className="text-destructive hover:text-destructive"
                                        >
                                            <X className="size-4" />
                                        </Button>
                                    )}
                                </TableCell>
                            </TableRow>
                        )
                    })}
                </TableBody>
            </Table>
        </div>
    )
}

function InvitationsTab() {
    const { data, isLoading } = useInvites()
    const resendInvite = useResendInvite()
    const revokeInvite = useRevokeInvite()

    const handleResend = async (inviteId: string) => {
        try {
            await resendInvite.mutateAsync(inviteId)
            toast.success("Invitation resent")
        } catch (error) {
            toast.error("Failed to resend", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
    }

    const handleRevoke = async (inviteId: string) => {
        if (!confirm("Revoke this invitation?")) return

        try {
            await revokeInvite.mutateAsync(inviteId)
            toast.success("Invitation revoked")
        } catch (error) {
            toast.error("Failed to revoke", {
                description: error instanceof Error ? error.message : "Unknown error",
            })
        }
    }

    const pendingInvites = data?.invites.filter(inv => inv.status === "pending") || []

    if (isLoading) {
        return (
            <div className="flex justify-center py-8">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (pendingInvites.length === 0) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                No pending invitations
            </div>
        )
    }

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Resends</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {pendingInvites.map((invite) => (
                    <TableRow key={invite.id}>
                        <TableCell className="font-medium">{invite.email}</TableCell>
                        <TableCell>
                            <Badge className={ROLE_COLORS[invite.role] || "bg-gray-100"}>
                                {ROLE_LABELS[invite.role] || invite.role}
                            </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                            {invite.expires_at
                                ? formatDistanceToNow(new Date(invite.expires_at), { addSuffix: true })
                                : "Never"}
                        </TableCell>
                        <TableCell>{invite.resend_count}/3</TableCell>
                        <TableCell className="text-right space-x-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleResend(invite.id)}
                                disabled={!invite.can_resend || resendInvite.isPending}
                            >
                                <RotateCcw className="size-4" />
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRevoke(invite.id)}
                                disabled={revokeInvite.isPending}
                                className="text-destructive hover:text-destructive"
                            >
                                <X className="size-4" />
                            </Button>
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

export default function TeamSettingsPage() {
    const [showInviteModal, setShowInviteModal] = useState(false)
    const { data: inviteData } = useInvites()
    const { data: members } = useMembers()
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const pendingCount = inviteData?.pending_count || 0
    const memberCount = members?.length || 0

    return (
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-5xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Team Management</h1>
                    <p className="text-sm text-muted-foreground">
                        Manage team members, roles, and permissions
                    </p>
                </div>

                <div className="flex gap-2">
                    <Link href="/settings/team/roles">
                        <Button variant="outline">
                            <Shield className="size-4 mr-2" />
                            Role Permissions
                        </Button>
                    </Link>
                    <Dialog open={showInviteModal} onOpenChange={setShowInviteModal}>
                        <DialogTrigger render={
                            <Button>
                                <UserPlus className="size-4 mr-2" />
                                Invite Member
                            </Button>
                        } />
                        <InviteTeamModal onClose={() => setShowInviteModal(false)} />
                    </Dialog>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Team</CardTitle>
                    <CardDescription>
                        {memberCount} member{memberCount !== 1 ? "s" : ""} • {pendingCount} pending invitation{pendingCount !== 1 ? "s" : ""}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Tabs defaultValue="members">
                        <TabsList className="mb-4">
                            <TabsTrigger value="members">
                                <Users className="size-4 mr-1" />
                                Members ({memberCount})
                            </TabsTrigger>
                            <TabsTrigger value="invitations">
                                <Mail className="size-4 mr-1" />
                                Invitations ({pendingCount})
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
    )
}
