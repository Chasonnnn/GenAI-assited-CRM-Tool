"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableHead, TableHeader, TableBody, TableRow, TableCell } from "@/components/ui/table"
import { ArrowLeftIcon, VideoIcon, CheckCircleIcon, UnlinkIcon, Loader2Icon, ExternalLinkIcon, CalendarIcon } from "lucide-react"
import { useZoomStatus, useZoomMeetings, useConnectZoom, useDisconnectIntegration, type ZoomMeetingRead } from "@/lib/hooks/use-user-integrations"
import Link from "@/components/app-link"
import { formatRelativeTime } from "@/lib/formatters"

export default function ZoomSettingsPage() {
    const { data: status, isLoading: statusLoading } = useZoomStatus()
    const { data: meetings = [], isLoading: meetingsLoading } = useZoomMeetings({ limit: 20 })
    const connectZoom = useConnectZoom()
    const disconnectZoom = useDisconnectIntegration()

    if (statusLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    const handleConnect = () => {
        connectZoom.mutate()
    }

    const handleDisconnect = () => {
        disconnectZoom.mutate('zoom')
    }

    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" render={<Link href="/settings/integrations" />}>
                    <ArrowLeftIcon className="h-5 w-5" />
                </Button>
                <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                        <VideoIcon className="size-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-semibold">Zoom Integration</h1>
                        <p className="text-sm text-muted-foreground">Manage your Zoom connection and view appointment history</p>
                    </div>
                </div>
            </div>

            {/* Connection Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle>Connection Status</CardTitle>
                </CardHeader>
                <CardContent>
                    {status?.connected ? (
                        <div className="space-y-4">
                            <div className="flex items-center gap-3">
                                <Badge variant="default" className="bg-green-600">
                                    <CheckCircleIcon className="mr-1 size-3" />
                                    Connected
                                </Badge>
                            </div>
                            <div className="space-y-2 text-sm">
                                <p>
                                    <span className="text-muted-foreground">Account:</span>{" "}
                                    <span className="font-medium">{status.account_email}</span>
                                </p>
                                {status.connected_at && (
                                    <p>
                                        <span className="text-muted-foreground">Connected:</span>{" "}
                                        <span className="font-medium">
                                            {formatRelativeTime(status.connected_at, "Unknown")}
                                        </span>
                                    </p>
                                )}
                                {status.token_expires_at && (
                                    <p>
                                        <span className="text-muted-foreground">Token expires:</span>{" "}
                                        <span className="font-medium">
                                            {formatRelativeTime(status.token_expires_at, "Unknown")}
                                        </span>
                                    </p>
                                )}
                            </div>
                            <div className="flex gap-2 pt-2">
                                <Button
                                    variant="outline"
                                    onClick={handleConnect}
                                    disabled={connectZoom.isPending}
                                >
                                    {connectZoom.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                    Reconnect
                                </Button>
                                <Button
                                    variant="destructive"
                                    onClick={handleDisconnect}
                                    disabled={disconnectZoom.isPending}
                                >
                                    {disconnectZoom.isPending ? (
                                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    ) : (
                                        <UnlinkIcon className="mr-2 size-4" />
                                    )}
                                    Disconnect
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <p className="text-sm text-muted-foreground">
                                Connect your Zoom account to schedule appointments directly from cases and intended parents.
                            </p>
                            <Button onClick={handleConnect} disabled={connectZoom.isPending}>
                                {connectZoom.isPending ? (
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                ) : (
                                    <VideoIcon className="mr-2 size-4" />
                                )}
                                Connect Zoom
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Appointment History */}
            {status?.connected && (
                <Card>
                    <CardHeader>
                        <CardTitle>Appointment History</CardTitle>
                        <CardDescription>Recent Zoom appointments created via the app</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {meetingsLoading ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : meetings.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                                <CalendarIcon className="h-12 w-12 text-muted-foreground/50 mb-3" />
                                <p className="text-sm font-medium text-muted-foreground">No appointments yet</p>
                                <p className="text-xs text-muted-foreground/60 mt-1">
                                    Appointments created from surrogates will appear here
                                </p>
                            </div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Topic</TableHead>
                                        <TableHead>Date</TableHead>
                                        <TableHead>Duration</TableHead>
                                        <TableHead>Surrogate</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {meetings.map((meeting: ZoomMeetingRead) => (
                                        <TableRow key={meeting.id}>
                                            <TableCell className="font-medium">{meeting.topic}</TableCell>
                                            <TableCell>
                                                {meeting.start_time
                                                    ? new Date(meeting.start_time).toLocaleDateString()
                                                    : "Instant"}
                                            </TableCell>
                                            <TableCell>{meeting.duration} min</TableCell>
                                            <TableCell>
                                                {meeting.surrogate_id ? (
                                                    <Link
                                                        href={`/surrogates/${meeting.surrogate_id}`}
                                                        className="text-teal-600 hover:underline"
                                                    >
                                                        View Surrogate
                                                    </Link>
                                                ) : meeting.intended_parent_id ? (
                                                    <Link
                                                        href={`/intended-parents/${meeting.intended_parent_id}`}
                                                        className="text-teal-600 hover:underline"
                                                    >
                                                        View IP
                                                    </Link>
                                                ) : (
                                                    <span className="text-muted-foreground">-</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <a
                                                    href={meeting.join_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center justify-center h-8 w-8 rounded-md hover:bg-accent hover:text-accent-foreground"
                                                >
                                                    <ExternalLinkIcon className="size-4" />
                                                </a>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
