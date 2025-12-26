"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { RefreshCwIcon, AlertTriangleIcon, UsersIcon, InfoIcon } from "lucide-react"

interface RecipientPreviewCardProps {
    totalCount: number
    sampleRecipients: { email: string; name: string | null }[]
    isLoading: boolean
    onRefresh: () => void
}

function getInitials(name: string | null, email: string): string {
    if (name) {
        const parts = name.split(" ")
        return parts.length > 1
            ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
            : name.slice(0, 2).toUpperCase()
    }
    return email.slice(0, 2).toUpperCase()
}

export function RecipientPreviewCard({
    totalCount,
    sampleRecipients,
    isLoading,
    onRefresh,
}: RecipientPreviewCardProps) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-lg">
                        <UsersIcon className="size-5" />
                        Recipient Preview
                    </CardTitle>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onRefresh}
                        disabled={isLoading}
                        className="gap-1.5"
                    >
                        <RefreshCwIcon className={`size-4 ${isLoading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Count Display */}
                {isLoading ? (
                    <div className="flex flex-col items-center py-4">
                        <Skeleton className="h-12 w-24 mb-2" />
                        <Skeleton className="h-4 w-32" />
                    </div>
                ) : totalCount === 0 ? (
                    <div className="flex flex-col items-center py-6 text-center">
                        <div className="rounded-full bg-amber-100 dark:bg-amber-900/30 p-3 mb-3">
                            <AlertTriangleIcon className="size-6 text-amber-600 dark:text-amber-400" />
                        </div>
                        <p className="font-medium text-amber-700 dark:text-amber-400">
                            No matching recipients
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                            Adjust your filter settings to find recipients
                        </p>
                    </div>
                ) : (
                    <div className="flex flex-col items-center py-4">
                        <span className="text-4xl font-bold tabular-nums">
                            {totalCount.toLocaleString()}
                        </span>
                        <span className="text-sm text-muted-foreground">
                            matching recipients
                        </span>
                    </div>
                )}

                {/* Sample Recipients */}
                {!isLoading && totalCount > 0 && sampleRecipients.length > 0 && (
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                Sample Recipients
                            </span>
                            <Badge variant="secondary" className="text-xs">
                                {sampleRecipients.length} of {totalCount}
                            </Badge>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {sampleRecipients.slice(0, 5).map((recipient, index) => (
                                <div
                                    key={index}
                                    className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 flex-shrink-0 max-w-[200px]"
                                >
                                    <Avatar className="size-7">
                                        <AvatarFallback className="text-xs bg-primary/10 text-primary">
                                            {getInitials(recipient.name, recipient.email)}
                                        </AvatarFallback>
                                    </Avatar>
                                    <div className="flex flex-col">
                                        <span className="text-sm font-medium truncate max-w-[140px]">
                                            {recipient.name || recipient.email.split("@")[0]}
                                        </span>
                                        <span className="text-xs text-muted-foreground truncate max-w-[140px]">
                                            {recipient.email}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Loading skeletons for recipients */}
                {isLoading && (
                    <div className="space-y-2">
                        <Skeleton className="h-4 w-28" />
                        <div className="flex gap-2">
                            {[...Array(3)].map((_, i) => (
                                <Skeleton key={i} className="h-14 w-44 rounded-lg" />
                            ))}
                        </div>
                    </div>
                )}

                {/* Info callout */}
                <div className="flex items-center gap-2 rounded-md bg-blue-50 dark:bg-blue-950/30 px-3 py-2 text-sm text-blue-700 dark:text-blue-300">
                    <InfoIcon className="size-4 shrink-0" />
                    <span>Preview based on current filter settings</span>
                </div>
            </CardContent>
        </Card>
    )
}
