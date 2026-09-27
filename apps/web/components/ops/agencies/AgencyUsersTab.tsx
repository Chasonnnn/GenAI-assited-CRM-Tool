"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Loader2, ShieldOff, UserCheck, UserMinus } from "lucide-react"
import { RelativeTime } from "@/components/ui/time-display"
import type { OrgMember } from "@/lib/api/platform"

type AgencyUsersTabProps = {
    members: OrgMember[]
    orgName: string
    mfaResetting: string | null
    onResetMfa: (member: OrgMember) => void
    onDeactivateMember: (memberId: string) => void
    onReactivateMember: (memberId: string) => void
    reactivating: string | null
}

export function AgencyUsersTab({
    members,
    orgName,
    mfaResetting,
    onResetMfa,
    onDeactivateMember,
    onReactivateMember,
    reactivating,
}: AgencyUsersTabProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Members</CardTitle>
            </CardHeader>
            <CardContent>
                {members.length === 0 ? (
                    <p className="text-center py-8 text-muted-foreground">No members yet</p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>User</TableHead>
                                <TableHead>Role</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Last Login</TableHead>
                                <TableHead className="w-32 text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {members.map((member) => (
                                <TableRow key={member.id}>
                                    <TableCell>
                                        <div>
                                            <div className="font-medium">{member.display_name}</div>
                                            <div className="text-sm text-muted-foreground">
                                                {member.email}
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline">{member.role}</Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={member.is_active ? "default" : "secondary"}>
                                            {member.is_active ? "Active" : "Inactive"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        <RelativeTime value={member.last_login_at} fallback="Never" />
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center justify-end gap-2">
                                            <AlertDialog>
                                                <AlertDialogTrigger
                                                    className={buttonVariants({
                                                        variant: "ghost",
                                                        size: "sm",
                                                    })}
                                                    aria-label={`Reset MFA for ${member.email}`}
                                                >
                                                    <ShieldOff className="size-4" />
                                                </AlertDialogTrigger>
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>Reset MFA and Duo?</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            This will clear CRM MFA state and Duo enrollment
                                                            for{" "}
                                                            <strong>{member.display_name}</strong> (
                                                            {member.email}). They will be required to set up
                                                            MFA again on next login, and the reset may fail if
                                                            Duo is unavailable.
                                                        </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                        <AlertDialogAction
                                                            onClick={() => onResetMfa(member)}
                                                            disabled={mfaResetting === member.id}
                                                        >
                                                            {mfaResetting === member.id ? (
                                                                <span className="inline-flex items-center gap-2">
                                                                    <Loader2 className="size-4 animate-spin" />
                                                                    Resetting
                                                                </span>
                                                            ) : (
                                                                "Reset MFA"
                                                            )}
                                                        </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                </AlertDialogContent>
                                            </AlertDialog>
                                            {member.is_active ? (
                                                <AlertDialog>
                                                    <AlertDialogTrigger
                                                        className={buttonVariants({
                                                            variant: "destructive-ghost",
                                                            size: "sm",
                                                            className: "text-muted-foreground",
                                                        })}
                                                        aria-label={`Deactivate ${member.email}`}
                                                    >
                                                        <UserMinus className="size-4" aria-hidden="true" />
                                                    </AlertDialogTrigger>
                                                    <AlertDialogContent>
                                                        <AlertDialogHeader>
                                                            <AlertDialogTitle>
                                                                Deactivate {member.display_name || member.email}?
                                                            </AlertDialogTitle>
                                                            <AlertDialogDescription>
                                                                <strong>{member.display_name || member.email}</strong> (
                                                                {member.email}) loses access to {orgName}. You can
                                                                reactivate them from the Members list.
                                                            </AlertDialogDescription>
                                                        </AlertDialogHeader>
                                                        <AlertDialogFooter>
                                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                            <AlertDialogAction
                                                                variant="destructive"
                                                                onClick={() =>
                                                                    onDeactivateMember(member.id)
                                                                }
                                                            >
                                                                Deactivate
                                                            </AlertDialogAction>
                                                        </AlertDialogFooter>
                                                    </AlertDialogContent>
                                                </AlertDialog>
                                            ) : (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => onReactivateMember(member.id)}
                                                    disabled={reactivating === member.id}
                                                    aria-label={`Reactivate ${member.email}`}
                                                >
                                                    {reactivating === member.id ? (
                                                        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                                                    ) : (
                                                        <UserCheck className="size-4" aria-hidden="true" />
                                                    )}
                                                    Reactivate
                                                </Button>
                                            )}
                                        </div>
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
