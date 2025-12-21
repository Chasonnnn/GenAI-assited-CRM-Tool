"use client"

import { formatDistanceToNow } from "date-fns"
import { useRouter } from "next/navigation"
import { Bell, Check, CheckCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useNotifications, useMarkRead, useMarkAllRead } from "@/lib/hooks/use-notifications"
import type { Notification } from "@/lib/api/notifications"

export default function NotificationsPage() {
    const router = useRouter()
    const { data, isLoading } = useNotifications({ limit: 50 })
    const markRead = useMarkRead()
    const markAllRead = useMarkAllRead()

    const notifications = data?.items ?? []
    const unreadCount = data?.unread_count ?? 0

    const handleNotificationClick = (notification: Notification) => {
        // Mark as read
        if (!notification.read_at) {
            markRead.mutate(notification.id)
        }

        // Navigate to entity
        if (notification.entity_type === "case" && notification.entity_id) {
            router.push(`/cases/${notification.entity_id}`)
        } else if (notification.entity_type === "task" && notification.entity_id) {
            router.push(`/tasks`)
        }
    }

    const handleMarkAllRead = () => {
        markAllRead.mutate()
    }

    if (isLoading) {
        return (
            <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-9 w-28" />
                </div>
                <div className="space-y-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full" />
                    ))}
                </div>
            </div>
        )
    }

    return (
        <div className="p-6">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <Bell className="h-6 w-6" />
                    <h1 className="text-2xl font-bold">Notifications</h1>
                    {unreadCount > 0 && (
                        <Badge variant="secondary">{unreadCount} unread</Badge>
                    )}
                </div>
                {unreadCount > 0 && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleMarkAllRead}
                        disabled={markAllRead.isPending}
                    >
                        <CheckCheck className="mr-2 h-4 w-4" />
                        Mark all read
                    </Button>
                )}
            </div>

            {notifications.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                        <Bell className="mx-auto h-12 w-12 mb-4 opacity-50" />
                        <p className="text-lg font-medium">No notifications</p>
                        <p className="text-sm">You're all caught up!</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {notifications.map((notification) => (
                        <Card
                            key={notification.id}
                            className={`cursor-pointer transition-colors hover:bg-muted/50 ${!notification.read_at ? "border-l-4 border-l-blue-500" : ""
                                }`}
                            onClick={() => handleNotificationClick(notification)}
                        >
                            <CardContent className="py-4">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <h3 className={`font-medium ${!notification.read_at ? "text-foreground" : "text-muted-foreground"}`}>
                                                {notification.title}
                                            </h3>
                                            {!notification.read_at && (
                                                <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                                            )}
                                        </div>
                                        {notification.body && (
                                            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                                                {notification.body}
                                            </p>
                                        )}
                                        <p className="text-xs text-muted-foreground mt-2">
                                            {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                                        </p>
                                    </div>
                                    {notification.read_at && (
                                        <Check className="h-4 w-4 text-muted-foreground shrink-0" />
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    )
}
