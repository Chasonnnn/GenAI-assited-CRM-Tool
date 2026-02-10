"use client"

import * as React from "react"
import { Bell } from "lucide-react"
import { useRouter } from "next/navigation"
import { formatDistanceToNow } from "date-fns"

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
    useNotifications,
    useUnreadCount,
    useMarkRead,
    useMarkAllRead,
} from "@/lib/hooks/use-notifications"
import { useNotificationSocket } from "@/lib/hooks/use-notification-socket"
import { useBrowserNotifications } from "@/lib/hooks/use-browser-notifications"
import type { Notification } from "@/lib/api/notifications"
import { getNotificationHref } from "@/lib/utils/notification-routing"

export function NotificationBell() {
    const router = useRouter()
    const { data: countData } = useUnreadCount()
    const { data: notificationsData } = useNotifications({ limit: 10 })
    const markRead = useMarkRead()
    const markAllRead = useMarkAllRead()

    // Real-time WebSocket connection
    const { lastNotification, unreadCount: wsUnreadCount } = useNotificationSocket()

    // Browser notifications
    const { permission, showNotification } = useBrowserNotifications()
    const lastNotificationIdRef = React.useRef<string | null>(null)

    // Show browser notification when new message arrives (only if tab not focused)
    React.useEffect(() => {
        if (
            lastNotification &&
            lastNotification.id &&
            lastNotification.id !== lastNotificationIdRef.current &&
            permission === 'granted' &&
            typeof document !== 'undefined' &&
            document.hidden // Only show if tab is not focused
        ) {
            lastNotificationIdRef.current = lastNotification.id
            const notificationOptions = {
                tag: lastNotification.id,
                ...(lastNotification.body ? { body: lastNotification.body } : {}),
                ...(lastNotification.entity_type ? { entityType: lastNotification.entity_type } : {}),
                ...(lastNotification.entity_id ? { entityId: lastNotification.entity_id } : {}),
                ...(lastNotification.type ? { notificationType: lastNotification.type } : {}),
            }
            showNotification(lastNotification.title || 'New notification', notificationOptions)
        }
    }, [lastNotification, permission, showNotification])

    // Prefer WebSocket count when connected, fall back to polling
    const unreadCount = wsUnreadCount ?? countData?.count ?? 0
    const notifications = notificationsData?.items ?? []

    const handleNotificationClick = (notification: Notification) => {
        // Mark as read
        if (!notification.read_at) {
            markRead.mutate(notification.id)
        }

        router.push(getNotificationHref(notification))
    }

    const handleMarkAllRead = () => {
        markAllRead.mutate()
    }

    const handleViewAll = () => {
        router.push("/notifications")
    }

    const label = unreadCount > 0
        ? `Notifications, ${unreadCount} unread`
        : "Notifications, no unread messages"

    return (
        <DropdownMenu>
            <DropdownMenuTrigger
                aria-label={label}
                className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "relative")}
            >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                    <Badge
                        variant="destructive"
                        className="absolute -top-1 -right-1 h-5 min-w-5 px-1 flex items-center justify-center text-xs"
                    >
                        {unreadCount > 99 ? "99+" : unreadCount}
                    </Badge>
                )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
                <div className="flex items-center justify-between px-3 py-2.5 text-xs text-muted-foreground">
                    <span className="font-medium">Notifications</span>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground"
                            onClick={handleMarkAllRead}
                        >
                            Mark all read
                        </Button>
                    )}
                </div>
                <DropdownMenuSeparator />

                {notifications.length === 0 ? (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                        No notifications
                    </div>
                ) : (
                    <ScrollArea className="h-[300px]">
                        {notifications.map((notification) => (
                            <DropdownMenuItem
                                key={notification.id}
                                className={`flex flex-col items-start gap-1 p-3 cursor-pointer ${!notification.read_at ? "bg-muted/50" : ""
                                    }`}
                                onClick={() => handleNotificationClick(notification)}
                            >
                                <div className="flex items-start justify-between w-full gap-2">
                                    <span className="font-medium text-sm line-clamp-1">
                                        {notification.title}
                                    </span>
                                    {!notification.read_at && (
                                        <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0 mt-1">
                                            <span className="sr-only">Unread</span>
                                        </span>
                                    )}
                                </div>
                                {notification.body && (
                                    <span className="text-xs text-muted-foreground line-clamp-2">
                                        {notification.body}
                                    </span>
                                )}
                                <span className="text-xs text-muted-foreground">
                                    {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                                </span>
                            </DropdownMenuItem>
                        ))}
                    </ScrollArea>
                )}

                <DropdownMenuSeparator />
                <DropdownMenuItem
                    className="justify-center text-sm font-medium"
                    onClick={handleViewAll}
                >
                    View all notifications
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
