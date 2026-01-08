"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Bell, BellOff, AlertTriangle, CheckCircle2, Loader2, FolderOpen, RefreshCw, ArrowRightLeft, ListChecks, CheckSquare, Calendar } from "lucide-react"
import { toast } from "sonner"
import { useState, useEffect } from "react"
import { useNotificationSettings, useUpdateNotificationSettings } from "@/lib/hooks/use-notifications"
import { useAuth } from "@/lib/auth-context"

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
                        <CheckCircle2 className="size-4" />
                        <span className="text-sm font-medium">Enabled</span>
                    </div>
                )
            case "denied":
                return (
                    <div className="flex items-center gap-2 text-red-600">
                        <BellOff className="size-4" />
                        <span className="text-sm font-medium">Blocked</span>
                    </div>
                )
            case "unsupported":
                return (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <AlertTriangle className="size-4" />
                        <span className="text-sm font-medium">Not Supported</span>
                    </div>
                )
            default:
                return (
                    <Button size="sm" onClick={handleRequestPermission} disabled={isRequesting}>
                        {isRequesting ? (
                            <Loader2 className="size-4 mr-2 animate-spin" />
                        ) : (
                            <Bell className="size-4 mr-2" />
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
                    <Bell className="size-5" />
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
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        )
    }

    // These match the NotificationSettings interface in notifications.ts
    const notificationTypes = [
        {
            key: "case_assigned",
            icon: FolderOpen,
            title: "Case Assigned",
            description: "When a case is assigned to you",
        },
        {
            key: "case_status_changed",
            icon: RefreshCw,
            title: "Case Status Changed",
            description: "When a case status is updated",
        },
        {
            key: "case_handoff",
            icon: ArrowRightLeft,
            title: "Case Handoff",
            description: "When a case is handed off to you",
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
    ]

    return (
        <Card>
            <CardHeader>
                <CardTitle>Email Notifications</CardTitle>
                <CardDescription>
                    Choose which notifications you want to receive via email at {user?.email}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {notificationTypes.map((type) => (
                    <div
                        key={type.key}
                        className="flex items-center justify-between p-4 rounded-lg border"
                    >
                        <div className="flex items-center gap-3">
                            <type.icon className="size-5 text-muted-foreground" />
                            <div>
                                <p className="font-medium">{type.title}</p>
                                <p className="text-sm text-muted-foreground">{type.description}</p>
                            </div>
                        </div>
                        <Switch
                            checked={settings?.[type.key as keyof typeof settings] ?? true}
                            onCheckedChange={(checked) => handleToggle(type.key, checked)}
                            disabled={updateSettings.isPending}
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
