"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Bell, BellOff, AlertTriangle, CheckCircle2, Loader2, FolderOpen, RefreshCw, ArrowRightLeft, ListChecks, CheckSquare, Calendar } from "lucide-react"
import { toast } from "sonner"
import { useState, useEffect } from "react"
import { useNotificationSettings, useUpdateNotificationSettings } from "@/lib/hooks/use-notifications"
import { useAuth } from "@/lib/auth-context"
import type { NotificationSettings } from "@/lib/api/notifications"

// Browser push notification card
function BrowserNotificationsCard() {
    const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default")
    const [isRequesting, setIsRequesting] = useState(false)

    useEffect(() => {
        if (typeof window !== "undefined" && "Notification" in window) {
            setPermission(Notification.permission)
        } else {
            setPermission("unsupported")
        }
    }, [])

    const handleRequestPermission = async () => {
        if (permission === "unsupported") {
            toast.error("Push notifications are not supported in your browser")
            return
        }

        setIsRequesting(true)
        try {
            const result = await Notification.requestPermission()
            setPermission(result)

            if (result === "granted") {
                toast.success("Browser notifications enabled!")
                new Notification("Notifications Enabled", {
                    body: "You'll now receive browser notifications for important updates.",
                    icon: "/favicon.ico",
                })
            } else if (result === "denied") {
                toast.error("Notifications were blocked. You can enable them in browser settings.")
            }
        } catch {
            toast.error("Failed to request notification permission")
        } finally {
            setIsRequesting(false)
        }
    }

    const getStatusDisplay = () => {
        switch (permission) {
            case "granted":
                return (
                    <div className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="size-4" aria-hidden="true" />
                        <span className="text-sm font-medium">Enabled</span>
                    </div>
                )
            case "denied":
                return (
                    <div className="flex items-center gap-2 text-red-600">
                        <BellOff className="size-4" aria-hidden="true" />
                        <span className="text-sm font-medium">Blocked</span>
                    </div>
                )
            case "unsupported":
                return (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <AlertTriangle className="size-4" aria-hidden="true" />
                        <span className="text-sm font-medium">Not Supported</span>
                    </div>
                )
            default:
                return (
                    <Button size="sm" onClick={handleRequestPermission} disabled={isRequesting}>
                        {isRequesting ? (
                            <Loader2 className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        ) : (
                            <Bell className="size-4 mr-2" aria-hidden="true" />
                        )}
                        Enable Notifications
                    </Button>
                )
        }
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Bell className="size-5" aria-hidden="true" />
                    Browser Notifications
                </CardTitle>
                <CardDescription>
                    Receive real-time notifications in your browser when important events occur.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="flex items-center justify-between p-4 rounded-lg border">
                    <div>
                        <p className="font-medium">Push Notifications</p>
                        <p className="text-sm text-muted-foreground">
                            {permission === "granted"
                                ? "You'll receive notifications even when the app is in the background."
                                : permission === "denied"
                                    ? "Notifications are blocked. Enable in browser settings."
                                    : "Enable push notifications to stay updated."}
                        </p>
                    </div>
                    {getStatusDisplay()}
                </div>
            </CardContent>
        </Card>
    )
}

// Notification preferences card matching actual API schema
function NotificationsSettingsCard() {
    const { user } = useAuth()
    const { data: settings, isLoading } = useNotificationSettings()
    const updateSettings = useUpdateNotificationSettings()

    const handleToggle = async (key: string, value: boolean) => {
        try {
            await updateSettings.mutateAsync({ [key]: value })
        } catch {
            toast.error("Failed to update notification settings")
        }
    }

    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-8">
                    <Loader2 className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </CardContent>
            </Card>
        )
    }

    // These match the NotificationSettings interface in notifications.ts
    const notificationTypes: Array<{
        key: keyof NotificationSettings
        icon: typeof Bell
        title: string
        description: string
    }> = [
        {
            key: "surrogate_assigned",
            icon: FolderOpen,
            title: "Surrogate Assigned",
            description: "When a surrogate is assigned to you",
        },
        {
            key: "surrogate_status_changed",
            icon: RefreshCw,
            title: "Surrogate Status Changed",
            description: "When a surrogate status is updated",
        },
        {
            key: "surrogate_claim_available",
            icon: ArrowRightLeft,
            title: "Surrogate Claim Available",
            description: "When a surrogate is ready to be claimed",
        },
        {
            key: "task_assigned",
            icon: CheckSquare,
            title: "Task Assigned",
            description: "When a task is assigned to you",
        },
        {
            key: "workflow_approvals",
            icon: ListChecks,
            title: "Workflow Approvals",
            description: "When workflow approvals are needed",
        },
        {
            key: "task_reminders",
            icon: AlertTriangle,
            title: "Task Reminders",
            description: "Reminders for upcoming task deadlines",
        },
        {
            key: "appointments",
            icon: Calendar,
            title: "Appointments",
            description: "Reminders for upcoming appointments",
        },
        {
            key: "contact_reminder",
            icon: RefreshCw,
            title: "Contact Reminders",
            description: "Follow-up reminders for assigned surrogates",
        },
        {
            key: "status_change_decisions",
            icon: ListChecks,
            title: "Status Change Decisions",
            description: "When status change requests are approved or rejected",
        },
        {
            key: "approval_timeouts",
            icon: AlertTriangle,
            title: "Approval Timeouts",
            description: "When workflow approvals expire before action is taken",
        },
        {
            key: "security_alerts",
            icon: AlertTriangle,
            title: "Security Alerts",
            description: "Security-relevant alerts such as quarantined attachments",
        },
    ]

    return (
        <Card>
            <CardHeader>
                <CardTitle>In-app Notifications</CardTitle>
                <CardDescription>
                    Choose which updates appear in-app for {user?.email}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {notificationTypes.map((type) => (
                    <div
                        key={type.key}
                        className="flex items-center justify-between p-4 rounded-lg border"
                    >
                        <div className="flex items-center gap-3">
                            <type.icon className="size-5 text-muted-foreground" aria-hidden="true" />
                            <div>
                                <p className="font-medium">{type.title}</p>
                                <p className="text-sm text-muted-foreground">{type.description}</p>
                            </div>
                        </div>
                        <Switch
                            checked={settings?.[type.key] ?? true}
                            onCheckedChange={(checked) => handleToggle(type.key, checked)}
                            disabled={updateSettings.isPending}
                            aria-label={`${type.title} notifications`}
                        />
                    </div>
                ))}
            </CardContent>
        </Card>
    )
}

export default function NotificationSettingsPage() {
    return (
        <div className="flex flex-1 flex-col gap-6 p-6 max-w-3xl mx-auto">
            <div>
                <h1 className="text-2xl font-semibold">Notifications</h1>
                <p className="text-sm text-muted-foreground">
                    Manage how you receive notifications and alerts
                </p>
            </div>

            <BrowserNotificationsCard />
            <NotificationsSettingsCard />
        </div>
    )
}
