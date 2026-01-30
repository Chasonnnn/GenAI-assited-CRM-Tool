"use client"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
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
import { Loader2, ShieldOff, UserMinus } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import type { OrgMember } from "@/lib/api/platform"

type AgencyUsersTabProps = {
    members: OrgMember[]
    orgName: string
    mfaResetting: string | null
    onResetMfa: (member: OrgMember) => void
    onDeactivateMember: (memberId: string) => void
}

export function AgencyUsersTab({
    members,
    orgName,
    mfaResetting,
    onResetMfa,
    onDeactivateMember,
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
                                <TableHead className="w-24 text-right">Actions</TableHead>
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
                                        {member.last_login_at
                                            ? formatDistanceToNow(new Date(member.last_login_at), {
                                                  addSuffix: true,
                                              })
                                            : "Never"}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center justify-end gap-2">
                                            <AlertDialog>
                                                <AlertDialogTrigger
                                                    className={buttonVariants({
                                                        variant: "ghost",
                                                        size: "sm",
                                                    })}
                                                >
                                                    <ShieldOff className="size-4" />
                                                </AlertDialogTrigger>
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>Reset MFA?</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            This will clear MFA enrollment for{" "}
                                                            <strong>{member.display_name}</strong> (
                                                            {member.email}). They will be required to set up
                                                            MFA again on next login.
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
                                            {member.is_active && (
                                                <AlertDialog>
                                                    <AlertDialogTrigger
                                                        className={buttonVariants({
                                                            variant: "ghost",
                                                            size: "sm",
                                                            className: "text-destructive",
                                                        })}
                                                    >
                                                        <UserMinus className="size-4" />
                                                    </AlertDialogTrigger>
                                                    <AlertDialogContent>
                                                        <AlertDialogHeader>
                                                            <AlertDialogTitle>Deactivate User?</AlertDialogTitle>
                                                            <AlertDialogDescription>
                                                                <strong>{member.display_name}</strong> (
                                                                {member.email}) will no longer be able to
                                                                access {orgName}. This action can be reversed.
                                                            </AlertDialogDescription>
                                                        </AlertDialogHeader>
                                                        <AlertDialogFooter>
                                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                            <AlertDialogAction
                                                                onClick={() =>
                                                                    onDeactivateMember(member.id)
                                                                }
                                                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                                            >
                                                                Deactivate
                                                            </AlertDialogAction>
                                                        </AlertDialogFooter>
                                                    </AlertDialogContent>
                                                </AlertDialog>
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
