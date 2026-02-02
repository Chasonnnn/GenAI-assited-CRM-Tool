"use client"

import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Ban, Loader2, Mail, Plus, RotateCw } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import type { OrgInvite, PlatformEmailStatus } from "@/lib/api/platform"
import Link from "@/components/app-link"
import {
    INVITE_ROLE_LABELS,
    INVITE_ROLE_OPTIONS,
    INVITE_STATUS_VARIANTS,
    type InviteRole,
} from "@/components/ops/agencies/agency-constants"

type AgencyInvitesTabProps = {
    orgName: string
    invites: OrgInvite[]
    inviteOpen: boolean
    inviteSubmitting: boolean
    inviteResending: string | null
    inviteForm: { email: string; role: InviteRole }
    inviteError: string | null
    platformEmailStatus: PlatformEmailStatus | null
    platformEmailLoading: boolean
    onInviteOpenChange: (open: boolean) => void
    onInviteEmailChange: (value: string) => void
    onInviteRoleChange: (value: InviteRole) => void
    onCreateInvite: () => void
    onResendInvite: (inviteId: string) => void
    onRevokeInvite: (inviteId: string) => void
}

export function AgencyInvitesTab({
    orgName,
    invites,
    inviteOpen,
    inviteSubmitting,
    inviteResending,
    inviteForm,
    inviteError,
    platformEmailStatus,
    platformEmailLoading,
    onInviteOpenChange,
    onInviteEmailChange,
    onInviteRoleChange,
    onCreateInvite,
    onResendInvite,
    onRevokeInvite,
}: AgencyInvitesTabProps) {
    const formatCooldown = (seconds: number) => {
        if (seconds <= 0) return "Resend available soon";
        if (seconds < 60) return `Resend in ${seconds}s`;
        const minutes = Math.ceil(seconds / 60);
        return `Resend in ${minutes}m`;
    };

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Invitations</CardTitle>
                <Dialog open={inviteOpen} onOpenChange={onInviteOpenChange}>
                    <DialogTrigger className={buttonVariants({ size: "sm" })}>
                        <Plus className="mr-2 size-4" />
                        Invite User
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Invite user</DialogTitle>
                            <DialogDescription>
                                Send an invitation to join {orgName}.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="invite-email">Email</Label>
                                <Input
                                    id="invite-email"
                                    type="email"
                                    value={inviteForm.email}
                                    onChange={(event) => onInviteEmailChange(event.target.value)}
                                    placeholder="user@agency.com"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="invite-role">Role</Label>
                                <Select
                                    value={inviteForm.role}
                                    onValueChange={(value) => {
                                        if (value) onInviteRoleChange(value as InviteRole)
                                    }}
                                >
                                    <SelectTrigger id="invite-role">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {INVITE_ROLE_OPTIONS.map((roleOption) => (
                                            <SelectItem key={roleOption} value={roleOption}>
                                                {INVITE_ROLE_LABELS[roleOption]}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            {inviteError && (
                                <p className="text-sm text-destructive">{inviteError}</p>
                            )}
                        </div>
                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => onInviteOpenChange(false)}
                                disabled={inviteSubmitting}
                            >
                                Cancel
                            </Button>
                            <Button onClick={onCreateInvite} disabled={inviteSubmitting}>
                                {inviteSubmitting ? "Sending..." : "Send invite"}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </CardHeader>
            <CardContent>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-600 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-300">
                    <div className="flex flex-col gap-1">
                        <span>
                            Invites use the platform <span className="font-mono">org_invite</span> system template.
                        </span>
                        <Link
                            href="/ops/templates?tab=system"
                            className={buttonVariants({ variant: "outline", size: "sm" })}
                        >
                            Open system templates
                        </Link>
                        {platformEmailLoading ? (
                            <span className="text-xs text-muted-foreground">
                                Loading sender status...
                            </span>
                        ) : platformEmailStatus?.configured ? (
                            <span className="text-xs text-muted-foreground">
                                Platform sender configured (Resend)
                            </span>
                        ) : (
                            <span className="text-xs text-yellow-700 dark:text-yellow-400">
                                Platform sender not configured — invite emails may fail.
                            </span>
                        )}
                    </div>
                </div>
                {invites.length === 0 ? (
                    <p className="text-center py-8 text-muted-foreground">No invites yet</p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Email</TableHead>
                                <TableHead>Role</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Opened</TableHead>
                                <TableHead>Clicked</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead className="w-10"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {invites.map((invite) => (
                                <TableRow key={invite.id}>
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            <Mail className="size-4 text-muted-foreground" />
                                            {invite.email}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline">{invite.role}</Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={INVITE_STATUS_VARIANTS[invite.status]}
                                        >
                                            {invite.status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {invite.open_count && invite.open_count > 0 ? (
                                            <div className="flex flex-col">
                                                <span>
                                                    {invite.open_count} open
                                                    {invite.open_count === 1 ? "" : "s"}
                                                </span>
                                                {invite.opened_at ? (
                                                    <span className="text-xs">
                                                        {formatDistanceToNow(
                                                            new Date(invite.opened_at),
                                                            { addSuffix: true }
                                                        )}
                                                    </span>
                                                ) : null}
                                            </div>
                                        ) : (
                                            "-"
                                        )}
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {invite.click_count && invite.click_count > 0 ? (
                                            <div className="flex flex-col">
                                                <span>
                                                    {invite.click_count} click
                                                    {invite.click_count === 1 ? "" : "s"}
                                                </span>
                                                {invite.clicked_at ? (
                                                    <span className="text-xs">
                                                        {formatDistanceToNow(
                                                            new Date(invite.clicked_at),
                                                            { addSuffix: true }
                                                        )}
                                                    </span>
                                                ) : null}
                                            </div>
                                        ) : (
                                            "-"
                                        )}
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {formatDistanceToNow(new Date(invite.created_at), {
                                            addSuffix: true,
                                        })}
                                    </TableCell>
                                    <TableCell>
                                        {invite.status === "pending" && (
                                            <div className="flex items-center gap-1">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => onResendInvite(invite.id)}
                                                    disabled={
                                                        inviteResending === invite.id ||
                                                        invite.can_resend === false
                                                    }
                                                    title={
                                                        invite.can_resend === false
                                                            ? invite.resend_cooldown_seconds
                                                                ? formatCooldown(invite.resend_cooldown_seconds)
                                                                : "Resend unavailable"
                                                            : "Resend invite"
                                                    }
                                                >
                                                    {inviteResending === invite.id ? (
                                                        <Loader2 className="size-4 animate-spin" />
                                                    ) : (
                                                        <RotateCw className="size-4" />
                                                    )}
                                                </Button>
                                                <AlertDialog>
                                                    <AlertDialogTrigger
                                                        className={buttonVariants({
                                                            variant: "ghost",
                                                            size: "sm",
                                                            className: "text-destructive",
                                                        })}
                                                    >
                                                        <Ban className="size-4" />
                                                    </AlertDialogTrigger>
                                                    <AlertDialogContent>
                                                        <AlertDialogHeader>
                                                            <AlertDialogTitle>Revoke Invite?</AlertDialogTitle>
                                                            <AlertDialogDescription>
                                                                The invite to <strong>{invite.email}</strong>{" "}
                                                                will be invalidated.
                                                            </AlertDialogDescription>
                                                        </AlertDialogHeader>
                                                        <AlertDialogFooter>
                                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                            <AlertDialogAction
                                                                onClick={() => onRevokeInvite(invite.id)}
                                                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                                            >
                                                                Revoke
                                                            </AlertDialogAction>
                                                        </AlertDialogFooter>
                                                    </AlertDialogContent>
                                                </AlertDialog>
                                            </div>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}
