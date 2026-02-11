"use client"

import * as React from "react"
import { Bell, BellOff, Loader2 } from "lucide-react"
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
    const { data: countData, isLoading: isCountLoading } = useUnreadCount()
    const { data: notificationsData, isLoading: isListLoading } = useNotifications({ limit: 10 })
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

    // Determine accessible label
    const ariaLabel = unreadCount > 0
        ? `Notifications (${unreadCount} unread)`
        : "Notifications (no unread)"

    const handleNotificationClick = (notification: Notification) => {
        // Mark as read
        if (!notification.read_at) {
            markRead.mutate(notification.id)
        }

        router.push(getNotificationHref(notification))
    }

    const handleMarkAllRead = (e: React.MouseEvent) => {
        e.preventDefault()
        markAllRead.mutate()
    }

    const handleViewAll = () => {
        router.push("/notifications")
    }

    return (
        <DropdownMenu>
            <DropdownMenuTrigger
                aria-label={ariaLabel}
                className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "relative")}
            >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                    <Badge
                        variant="destructive"
                        className="absolute -top-1 -right-1 h-5 min-w-5 px-1 flex items-center justify-center text-xs pointer-events-none"
                        aria-hidden="true"
                    >
                        {unreadCount > 99 ? "99+" : unreadCount}
                    </Badge>
                )}
                {/* Visual loading indicator if initially loading and no count yet */}
                {isCountLoading && wsUnreadCount === null && countData === undefined && (
                     <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-muted-foreground animate-pulse" aria-hidden="true" />
                )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
                <div className="flex items-center justify-between px-3 py-2.5 text-xs text-muted-foreground">
                    <span className="font-medium">Notifications</span>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-1"
                            onClick={handleMarkAllRead}
                            disabled={markAllRead.isPending}
                        >
                            {markAllRead.isPending ? "Marking..." : "Mark all read"}
                        </Button>
                    )}
                </div>
                <DropdownMenuSeparator />

                {isListLoading && notifications.length === 0 ? (
                     <div className="flex flex-col items-center justify-center py-8 text-muted-foreground space-y-2">
                        <Loader2 className="h-8 w-8 animate-spin opacity-50" />
                        <p className="text-sm">Loading notifications...</p>
                    </div>
                ) : notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground space-y-2">
                        <BellOff className="h-8 w-8 opacity-20" aria-hidden="true" />
                        <p className="text-sm font-medium">No notifications</p>
                        <p className="text-xs text-muted-foreground/80 text-center px-4">
                            You're all caught up! Check back later for updates.
                        </p>
                    </div>
                ) : (
                    <ScrollArea className="h-[300px]">
                        {notifications.map((notification) => (
                            <DropdownMenuItem
                                key={notification.id}
                                className={cn(
                                    "flex flex-col items-start gap-1 p-3 cursor-pointer focus:bg-accent focus:text-accent-foreground",
                                    !notification.read_at && "bg-muted/30"
                                )}
                                onClick={() => handleNotificationClick(notification)}
                            >
                                <div className="flex items-start justify-between w-full gap-2">
                                    <span className={cn("text-sm line-clamp-1", !notification.read_at ? "font-semibold" : "font-medium")}>
                                        {notification.title}
                                    </span>
                                    {!notification.read_at && (
                                        <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0 mt-1" aria-hidden="true" />
                                    )}
                                </div>
                                {notification.body && (
                                    <span className="text-xs text-muted-foreground line-clamp-2">
                                        {notification.body}
                                    </span>
                                )}
                                <span className="text-[10px] text-muted-foreground/70">
                                    {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                                </span>
                            </DropdownMenuItem>
                        ))}
                    </ScrollArea>
                )}

                <DropdownMenuSeparator />
                <DropdownMenuItem
                    className="justify-center text-sm font-medium py-2 cursor-pointer text-primary"
                    onClick={handleViewAll}
                >
                    View all notifications
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
