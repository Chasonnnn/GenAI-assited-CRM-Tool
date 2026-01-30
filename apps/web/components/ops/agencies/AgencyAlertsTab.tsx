"use client"

import { AlertTriangle, Loader2 } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import type { PlatformAlert } from "@/lib/api/platform"
import { ALERT_SEVERITY_BADGES, ALERT_STATUS_BADGES } from "@/components/ops/agencies/agency-constants"

type AgencyAlertsTabProps = {
    orgAlerts: PlatformAlert[]
    alertsLoading: boolean
    alertsUpdating: string | null
    onRefresh: () => void
    onAcknowledge: (alertId: string) => void
    onResolve: (alertId: string) => void
}

export function AgencyAlertsTab({
    orgAlerts,
    alertsLoading,
    alertsUpdating,
    onRefresh,
    onAcknowledge,
    onResolve,
}: AgencyAlertsTabProps) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Organization Alerts</CardTitle>
                <Button variant="outline" size="sm" onClick={onRefresh} disabled={alertsLoading}>
                    {alertsLoading ? "Refreshing..." : "Refresh"}
                </Button>
            </CardHeader>
            <CardContent>
                {alertsLoading ? (
                    <div className="flex items-center justify-center py-10">
                        <Loader2 className="size-6 animate-spin text-muted-foreground" />
                    </div>
                ) : orgAlerts.length === 0 ? (
                    <div className="text-center py-10">
                        <AlertTriangle className="size-10 mx-auto mb-3 text-muted-foreground/50" />
                        <p className="text-muted-foreground">No alerts for this organization</p>
                    </div>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Alert</TableHead>
                                <TableHead>Severity</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Last Seen</TableHead>
                                <TableHead className="w-32"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {orgAlerts.map((alert) => (
                                <TableRow key={alert.id}>
                                    <TableCell>
                                        <div>
                                            <div className="font-medium">{alert.title}</div>
                                            <div className="text-sm text-muted-foreground">
                                                {alert.alert_type}
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={ALERT_SEVERITY_BADGES[alert.severity]}
                                        >
                                            {alert.severity}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={ALERT_STATUS_BADGES[alert.status]}
                                        >
                                            {alert.status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {formatDistanceToNow(new Date(alert.last_seen_at), {
                                            addSuffix: true,
                                        })}
                                    </TableCell>
                                    <TableCell>
                                        {alert.status !== "resolved" && (
                                            <div className="flex items-center gap-2">
                                                {alert.status === "open" && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => onAcknowledge(alert.id)}
                                                        disabled={alertsUpdating === alert.id}
                                                    >
                                                        Acknowledge
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => onResolve(alert.id)}
                                                    disabled={alertsUpdating === alert.id}
                                                >
                                                    Resolve
                                                </Button>
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
