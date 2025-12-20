"use client"

import { useState } from "react"
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
import { Loader2, UserPlus, Mail, RotateCcw, X, Clock, Check, XCircle } from "lucide-react"
import { useInvites, useCreateInvite, useResendInvite, useRevokeInvite } from "@/lib/hooks/use-invites"
import { useToast } from "@/components/ui/use-toast"
import { formatDistanceToNow } from "date-fns"

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
    const [role, setRole] = useState("member")
    const createInvite = useCreateInvite()
    const { toast } = useToast()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        try {
            await createInvite.mutateAsync({ email, role })
            toast({
                title: "Invitation sent",
                description: `Invited ${email} as ${role}`,
            })
            onClose()
        } catch (error) {
            toast({
                title: "Failed to send invitation",
                description: error instanceof Error ? error.message : "Unknown error",
                variant: "destructive",
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
                        <Select value={role} onValueChange={setRole}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="member">Member</SelectItem>
                                <SelectItem value="manager">Manager</SelectItem>
                            </SelectContent>
                        </Select>
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

export default function TeamSettingsPage() {
    const [showInviteModal, setShowInviteModal] = useState(false)
    const { data, isLoading } = useInvites()
    const resendInvite = useResendInvite()
    const revokeInvite = useRevokeInvite()
    const { toast } = useToast()

    const handleResend = async (inviteId: string) => {
        try {
            await resendInvite.mutateAsync(inviteId)
            toast({ title: "Invitation resent" })
        } catch (error) {
            toast({
                title: "Failed to resend",
                description: error instanceof Error ? error.message : "Unknown error",
                variant: "destructive",
            })
        }
    }

    const handleRevoke = async (inviteId: string) => {
        if (!confirm("Revoke this invitation?")) return

        try {
            await revokeInvite.mutateAsync(inviteId)
            toast({ title: "Invitation revoked" })
        } catch (error) {
            toast({
                title: "Failed to revoke",
                description: error instanceof Error ? error.message : "Unknown error",
                variant: "destructive",
            })
        }
    }

    const pendingInvites = data?.invites.filter(inv => inv.status === "pending") || []
    const allInvites = data?.invites || []

    return (
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-5xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Team Management</h1>
                    <p className="text-sm text-muted-foreground">
                        Manage team members and pending invitations
                    </p>
                </div>

                <Dialog open={showInviteModal} onOpenChange={setShowInviteModal}>
                    <DialogTrigger asChild>
                        <Button>
                            <UserPlus className="size-4 mr-2" />
                            Invite Team Member
                        </Button>
                    </DialogTrigger>
                    <InviteTeamModal onClose={() => setShowInviteModal(false)} />
                </Dialog>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Invitations</CardTitle>
                    <CardDescription>
                        {data?.pending_count || 0} pending invitation{(data?.pending_count || 0) !== 1 ? "s" : ""}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Tabs defaultValue="pending">
                        <TabsList className="mb-4">
                            <TabsTrigger value="pending">
                                Pending ({pendingInvites.length})
                            </TabsTrigger>
                            <TabsTrigger value="all">
                                All History ({allInvites.length})
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="pending">
                            {isLoading ? (
                                <div className="flex justify-center py-8">
                                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : pendingInvites.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground">
                                    No pending invitations
                                </div>
                            ) : (
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
                                                    <Badge variant="secondary" className="capitalize">
                                                        {invite.role}
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
                                                        title={
                                                            invite.can_resend
                                                                ? "Resend invitation"
                                                                : invite.resend_cooldown_seconds
                                                                    ? `Wait ${invite.resend_cooldown_seconds}s`
                                                                    : "Max resends reached"
                                                        }
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
                            )}
                        </TabsContent>

                        <TabsContent value="all">
                            {isLoading ? (
                                <div className="flex justify-center py-8">
                                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : allInvites.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground">
                                    No invitation history
                                </div>
                            ) : (
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Role</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Created</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {allInvites.map((invite) => (
                                            <TableRow key={invite.id}>
                                                <TableCell className="font-medium">{invite.email}</TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary" className="capitalize">
                                                        {invite.role}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>{getStatusBadge(invite.status)}</TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {formatDistanceToNow(new Date(invite.created_at), { addSuffix: true })}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            )}
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>
        </div>
    )
}
