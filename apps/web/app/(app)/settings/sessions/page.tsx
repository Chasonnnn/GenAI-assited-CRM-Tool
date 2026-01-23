"use client"

/**
 * Session Management Page
 *
 * Allows users to view and manage their active sessions across devices.
 * Features:
 * - List all active sessions with device info
 * - Identify current session ("This device")
 * - Revoke individual sessions
 * - Revoke all other sessions
 */

import { useState } from "react"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    MonitorIcon,
    SmartphoneIcon,
    TabletIcon,
    GlobeIcon,
    Loader2Icon,
    LogOutIcon,
    ShieldCheckIcon,
} from "lucide-react"
import {
    useSessions,
    useRevokeSession,
    useRevokeAllSessions,
    type Session,
} from "@/lib/hooks/use-sessions"

// =============================================================================
// Device Icon Helper
// =============================================================================

function getDeviceIcon(deviceInfo: string | null) {
    if (!deviceInfo) return <GlobeIcon className="size-5" />

    const info = deviceInfo.toLowerCase()
    if (info.includes("mobile") || info.includes("iphone") || info.includes("android")) {
        return <SmartphoneIcon className="size-5" />
    }
    if (info.includes("tablet") || info.includes("ipad")) {
        return <TabletIcon className="size-5" />
    }
    return <MonitorIcon className="size-5" />
}

function parseDeviceInfo(deviceInfo: string | null): { browser: string; os: string } {
    if (!deviceInfo) {
        return { browser: "Unknown browser", os: "Unknown device" }
    }

    // Simple parsing - in production you'd use a proper user-agent parser
    let browser = "Unknown browser"
    let os = "Unknown device"

    if (deviceInfo.includes("Chrome")) browser = "Chrome"
    else if (deviceInfo.includes("Firefox")) browser = "Firefox"
    else if (deviceInfo.includes("Safari") && !deviceInfo.includes("Chrome")) browser = "Safari"
    else if (deviceInfo.includes("Edge")) browser = "Edge"

    if (deviceInfo.includes("Windows")) os = "Windows"
    else if (deviceInfo.includes("Mac")) os = "macOS"
    else if (deviceInfo.includes("Linux")) os = "Linux"
    else if (deviceInfo.includes("iPhone")) os = "iPhone"
    else if (deviceInfo.includes("iPad")) os = "iPad"
    else if (deviceInfo.includes("Android")) os = "Android"

    return { browser, os }
}

// =============================================================================
// Session Card Component
// =============================================================================

function SessionCard({
    session,
    onRevoke,
    isRevoking,
}: {
    session: Session
    onRevoke: () => void
    isRevoking: boolean
}) {
    const { browser, os } = parseDeviceInfo(session.device_info)
    const lastActive = session.last_active_at
        ? formatDistanceToNow(new Date(session.last_active_at), { addSuffix: true })
        : "Unknown"

    return (
        <div className="flex items-start justify-between gap-4 rounded-lg border p-4">
            <div className="flex gap-4">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    {getDeviceIcon(session.device_info)}
                </div>
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <p className="font-medium">{browser} on {os}</p>
                        {session.is_current && (
                            <Badge variant="outline" className="text-xs text-green-600 border-green-200 bg-green-50">
                                This device
                            </Badge>
                        )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                        {session.ip_address || "Unknown IP"} · Last active {lastActive}
                    </p>
                </div>
            </div>

            {!session.is_current && (
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onRevoke}
                    disabled={isRevoking}
                    className="shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                    {isRevoking ? (
                        <Loader2Icon className="size-4 animate-spin" />
                    ) : (
                        <>
                            <LogOutIcon className="size-4 mr-1" />
                            Revoke
                        </>
                    )}
                </Button>
            )}
        </div>
    )
}

// =============================================================================
// Main Component
// =============================================================================

export default function SessionsPage() {
    const { data: sessions, isLoading, error } = useSessions()
    const revokeSession = useRevokeSession()
    const revokeAllSessions = useRevokeAllSessions()

    const [showRevokeAllDialog, setShowRevokeAllDialog] = useState(false)
    const [revokingSessionId, setRevokingSessionId] = useState<string | null>(null)

    const handleRevokeSession = async (sessionId: string) => {
        setRevokingSessionId(sessionId)
        try {
            await revokeSession.mutateAsync(sessionId)
            toast.success("Session revoked successfully")
        } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to revoke session")
        } finally {
            setRevokingSessionId(null)
        }
    }

    const handleRevokeAllSessions = async () => {
        try {
            const result = await revokeAllSessions.mutateAsync()
            setShowRevokeAllDialog(false)
            toast.success(`Revoked ${result.count} session${result.count !== 1 ? "s" : ""}`)
        } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to revoke sessions")
        }
    }

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="container max-w-2xl py-8">
                <Card>
                    <CardContent className="py-8 text-center">
                        <p className="text-destructive">Failed to load sessions</p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    const otherSessions = sessions?.filter(s => !s.is_current) || []
    const currentSession = sessions?.find(s => s.is_current)

    return (
        <div className="container max-w-2xl py-8 space-y-6">
            <div>
                <h1 className="text-2xl font-semibold">Active Sessions</h1>
                <p className="text-muted-foreground">
                    Manage devices where you're currently logged in.
                </p>
            </div>

            {/* Current Session */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                        <ShieldCheckIcon className="size-5 text-green-500" />
                        Current Session
                    </CardTitle>
                    <CardDescription>
                        This is the device you're using right now.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {currentSession ? (
                        <SessionCard
                            session={currentSession}
                            onRevoke={() => {}}
                            isRevoking={false}
                        />
                    ) : (
                        <p className="text-sm text-muted-foreground">
                            Unable to identify current session.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Other Sessions */}
            <Card>
                <CardHeader className="flex flex-row items-start justify-between space-y-0">
                    <div>
                        <CardTitle className="text-lg">Other Sessions</CardTitle>
                        <CardDescription>
                            {otherSessions.length === 0
                                ? "No other active sessions."
                                : `${otherSessions.length} other active session${otherSessions.length !== 1 ? "s" : ""}`}
                        </CardDescription>
                    </div>
                    {otherSessions.length > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowRevokeAllDialog(true)}
                            className="shrink-0"
                        >
                            <LogOutIcon className="size-4 mr-2" />
                            Revoke All
                        </Button>
                    )}
                </CardHeader>
                <CardContent>
                    {otherSessions.length === 0 ? (
                        <div className="py-8 text-center text-muted-foreground">
                            <MonitorIcon className="size-8 mx-auto mb-2 opacity-50" />
                            <p>You're only logged in on this device.</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {otherSessions.map(session => (
                                <SessionCard
                                    key={session.id}
                                    session={session}
                                    onRevoke={() => handleRevokeSession(session.id)}
                                    isRevoking={revokingSessionId === session.id}
                                />
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Revoke All Confirmation Dialog */}
            <Dialog open={showRevokeAllDialog} onOpenChange={setShowRevokeAllDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Revoke All Other Sessions?</DialogTitle>
                        <DialogDescription>
                            This will log you out of all other devices. You'll remain logged in on this device.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setShowRevokeAllDialog(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleRevokeAllSessions}
                            disabled={revokeAllSessions.isPending}
                        >
                            {revokeAllSessions.isPending ? (
                                <>
                                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                                    Revoking...
                                </>
                            ) : (
                                "Revoke All Sessions"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
