"use client"

import type { Route } from "next"
import Link from "next/link"
import { Bell, BellOff, CircleCheck } from "lucide-react"
import { useRouter } from "next/navigation"
import { formatDistanceToNow } from "date-fns"
import { useState, type Dispatch, type SetStateAction } from "react"

import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"
import {
    useNotifications,
    useNotificationCounts,
    useMarkRead,
    useMarkAllRead,
} from "@/lib/hooks/use-notifications"
import { useNotificationSocket } from "@/lib/hooks/use-notification-socket"
import { useBrowserNotifications } from "@/lib/hooks/use-browser-notifications"
import { useBrowserNotificationDelivery } from "@/lib/hooks/use-browser-notification-delivery"
import type { Notification, NotificationTier } from "@/lib/api/notifications"
import { getNotificationHref } from "@/lib/utils/notification-routing"
import { useMountEffect } from "@/lib/hooks/use-mount-effect"
import { consumeLoginNotificationReminder } from "@/lib/notifications/login-reminder"

const PANEL_LIMIT = 30

function OpenLoginNotificationReminder({
    setOpen,
}: {
    setOpen: Dispatch<SetStateAction<boolean>>
}) {
    useMountEffect(() => {
        if (consumeLoginNotificationReminder()) {
            setOpen(true)
        }
    })

    return null
}

function ConsumeLoginNotificationReminder() {
    useMountEffect(() => {
        consumeLoginNotificationReminder()
    })

    return null
}

function getTriggerLabel(actionCount: number, updatesUnread: number) {
    if (actionCount > 0) return `Notifications (${actionCount} need action)`
    if (updatesUnread > 0) return `Notifications (${updatesUnread} unread updates)`
    return "Notifications"
}

function NotificationList({
    tier,
    enabled,
    pollWhileOpen,
    onSelect,
}: {
    tier: NotificationTier
    enabled: boolean
    pollWhileOpen: boolean
    onSelect: (notification: Notification) => void
}) {
    const { data, isLoading, isError, refetch, isFetching } = useNotifications({
        tier,
        limit: PANEL_LIMIT,
        enabled,
        refetch_interval_ms: enabled && pollWhileOpen ? 30_000 : false,
    })
    const notifications = data?.items ?? []

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
                <Spinner aria-label="Loading notifications" />
                <span>Loading notifications</span>
            </div>
        )
    }

    if (isError) {
        return (
            <div className="flex flex-col items-center justify-center gap-3 py-10 text-sm text-muted-foreground">
                <span>Couldn&apos;t load notifications</span>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void refetch()}
                    disabled={isFetching}
                    aria-busy={isFetching}
                >
                    {isFetching && <Spinner className="size-3" aria-hidden="true" />}
                    Retry
                </Button>
            </div>
        )
    }

    if (notifications.length === 0) {
        const Icon = tier === "action" ? CircleCheck : BellOff
        return (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
                <Icon className="size-5" aria-hidden="true" />
                <span>{tier === "action" ? "Nothing needs you" : "No updates"}</span>
            </div>
        )
    }

    return (
        <ul className="divide-y">
            {notifications.map((notification) => {
                const isUnread = !notification.read_at
                return (
                    <li key={notification.id}>
                        <Button
                            variant="ghost"
                            className={cn(
                                "h-auto w-full flex-col items-start justify-start gap-1 rounded-none px-4 py-3 text-left font-normal whitespace-normal",
                                isUnread && "bg-muted/50"
                            )}
                            onClick={() => onSelect(notification)}
                        >
                            <span className="flex w-full items-start justify-between gap-2">
                                <span className="line-clamp-2 text-sm font-medium">
                                    {notification.title}
                                </span>
                                {isUnread && (
                                    <>
                                        <span className="sr-only">Unread</span>
                                        <span
                                            aria-hidden="true"
                                            className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
                                        />
                                    </>
                                )}
                            </span>
                            {notification.body && (
                                <span className="line-clamp-2 text-xs text-muted-foreground">
                                    {notification.body}
                                </span>
                            )}
                            <span className="text-xs text-muted-foreground" suppressHydrationWarning>
                                {formatDistanceToNow(parseDateInput(notification.created_at), {
                                    addSuffix: true,
                                })}
                            </span>
                        </Button>
                    </li>
                )
            })}
        </ul>
    )
}

export function NotificationBell() {
    const { push } = useRouter()
    const [isOpen, setIsOpen] = useState(false)
    const [tab, setTab] = useState<NotificationTier>("action")

    // Real-time WebSocket connection; pushed counts land in the count query.
    const { isConnected, lastNotification } = useNotificationSocket()
    const { data: counts, isLoading: isCountLoading } = useNotificationCounts()
    const markRead = useMarkRead()
    const markAllRead = useMarkAllRead()

    // Browser notifications
    const { isSupported, permission, requestPermission, showNotification } =
        useBrowserNotifications()
    useBrowserNotificationDelivery({
        latest: lastNotification,
        permission,
        showNotification,
    })

    const actionCount = counts?.action_count ?? 0
    const updatesUnread = counts?.updates_unread ?? 0
    // Remounting the icon on each new action item replays the ring animation.
    const ringKey = lastNotification?.tier === "action" ? lastNotification.id : undefined

    const handleSelect = (notification: Notification) => {
        if (!notification.read_at) {
            markRead.mutate(notification.id)
        }
        setIsOpen(false)
        push(getNotificationHref(notification) as Route)
    }

    const handleEnableDesktopAlerts = () => {
        void requestPermission().then((result) => {
            if (result === "granted") {
                toast.success("Desktop alerts on")
            } else if (result === "denied") {
                toast.error("Desktop alerts are blocked. Allow notifications in your browser settings.")
            }
        })
    }

    return (
        <>
            {!isCountLoading &&
                (actionCount > 0 ? (
                    <OpenLoginNotificationReminder setOpen={setIsOpen} />
                ) : (
                    <ConsumeLoginNotificationReminder />
                ))}
            <Button
                variant="ghost"
                size="icon"
                aria-label={getTriggerLabel(actionCount, updatesUnread)}
                aria-haspopup="dialog"
                aria-expanded={isOpen}
                className="relative"
                onClick={() => setIsOpen(true)}
            >
                <Bell
                    key={ringKey}
                    className={cn("size-5 origin-top", ringKey && "motion-safe:animate-bell-ring")}
                    aria-hidden="true"
                />
                {isCountLoading && (
                    <span
                        aria-hidden="true"
                        className="absolute -top-0.5 -right-0.5 size-2.5 animate-pulse rounded-full bg-muted-foreground/40"
                    />
                )}
                {actionCount > 0 ? (
                    <Badge
                        aria-hidden="true"
                        className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center px-1 text-xs tabular-nums"
                    >
                        {actionCount > 99 ? "99+" : actionCount}
                    </Badge>
                ) : updatesUnread > 0 ? (
                    <span
                        aria-hidden="true"
                        className="absolute top-1.5 right-1.5 size-2 rounded-full bg-muted-foreground"
                    />
                ) : null}
            </Button>
            <Sheet open={isOpen} onOpenChange={setIsOpen}>
                <SheetContent
                    side="right"
                    className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-md"
                    overlayClassName="bg-black/20 supports-backdrop-filter:backdrop-blur-none"
                >
                    <div className="flex h-14 shrink-0 items-center gap-2 pr-14 pl-4">
                        <SheetTitle className="text-base font-semibold">Notifications</SheetTitle>
                        {tab === "update" && updatesUnread > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="ml-auto text-xs text-muted-foreground hover:text-foreground"
                                onClick={() => markAllRead.mutate("update")}
                                disabled={markAllRead.isPending}
                                aria-busy={markAllRead.isPending}
                            >
                                {markAllRead.isPending && <Spinner className="size-3" aria-hidden="true" />}
                                Mark all read
                            </Button>
                        )}
                    </div>
                    <Tabs
                        value={tab}
                        onValueChange={(value) => setTab(value as NotificationTier)}
                        className="min-h-0 flex-1 gap-0"
                    >
                        <TabsList variant="line" className="w-full justify-start border-b px-3">
                            <TabsTrigger value="action" className="flex-none">
                                Action needed
                                {actionCount > 0 && (
                                    <Badge className="h-5 min-w-5 px-1.5 tabular-nums">
                                        {actionCount > 99 ? "99+" : actionCount}
                                    </Badge>
                                )}
                            </TabsTrigger>
                            <TabsTrigger value="update" className="flex-none">
                                Updates
                                {updatesUnread > 0 && (
                                    <>
                                        <span className="sr-only">({updatesUnread} unread)</span>
                                        <span aria-hidden="true" className="size-1.5 rounded-full bg-primary" />
                                    </>
                                )}
                            </TabsTrigger>
                        </TabsList>
                        {isSupported && permission === "default" && (
                            <div className="flex items-center gap-3 border-b bg-muted/50 px-4 py-2 text-xs">
                                <Bell className="size-3.5 text-muted-foreground" aria-hidden="true" />
                                <span className="flex-1">Desktop alerts are off</span>
                                <Button variant="outline" size="sm" onClick={handleEnableDesktopAlerts}>
                                    Turn on
                                </Button>
                            </div>
                        )}
                        <TabsContent value="action" className="min-h-0 flex-1 overflow-y-auto">
                            <NotificationList
                                tier="action"
                                enabled={isOpen}
                                pollWhileOpen={!isConnected}
                                onSelect={handleSelect}
                            />
                        </TabsContent>
                        <TabsContent value="update" className="min-h-0 flex-1 overflow-y-auto">
                            <NotificationList
                                tier="update"
                                enabled={isOpen}
                                pollWhileOpen={!isConnected}
                                onSelect={handleSelect}
                            />
                        </TabsContent>
                    </Tabs>
                    <div className="flex shrink-0 items-center justify-between border-t px-2 py-2">
                        <Link
                            href="/settings/notifications"
                            className={buttonVariants({ variant: "ghost", size: "sm" })}
                            onClick={() => setIsOpen(false)}
                        >
                            Settings
                        </Link>
                        <Link
                            href="/notifications"
                            className={buttonVariants({ variant: "ghost", size: "sm" })}
                            onClick={() => setIsOpen(false)}
                        >
                            View all
                        </Link>
                    </div>
                </SheetContent>
            </Sheet>
        </>
    )
}
