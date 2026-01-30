"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { formatDistanceToNow } from "date-fns"
import type { AdminActionLog } from "@/lib/api/platform"

type AgencyAuditTabProps = {
    actionLogs: AdminActionLog[]
}

export function AgencyAuditTab({ actionLogs }: AgencyAuditTabProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Admin Action Log</CardTitle>
                <CardDescription>
                    Platform admin actions related to this organization
                </CardDescription>
            </CardHeader>
            <CardContent>
                {actionLogs.length === 0 ? (
                    <p className="text-center py-8 text-muted-foreground">
                        No admin actions recorded
                    </p>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Action</TableHead>
                                <TableHead>Actor</TableHead>
                                <TableHead>Details</TableHead>
                                <TableHead>Time</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {actionLogs.map((log) => (
                                <TableRow key={log.id}>
                                    <TableCell className="font-mono text-sm">{log.action}</TableCell>
                                    <TableCell className="text-sm">
                                        {log.actor_email || "System"}
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                                        {log.metadata ? JSON.stringify(log.metadata) : "-"}
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {formatDistanceToNow(new Date(log.created_at), {
                                            addSuffix: true,
                                        })}
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
