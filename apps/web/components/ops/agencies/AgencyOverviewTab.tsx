"use client"

import { useState } from "react"
import type { ReactNode } from "react"
import { format } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Loader2 } from "lucide-react"
import { UtcDate } from "@/components/ui/time-display"
import type { OrganizationDetail } from "@/lib/api/platform"

function DetailRow({
    label,
    value,
    mono = false,
}: {
    label: string
    value: ReactNode
    mono?: boolean
}) {
    return (
        <div className="flex justify-between gap-4 py-2 border-b border-border last:border-0">
            <span className="text-muted-foreground">{label}</span>
            <span
                className={`min-w-0 text-right text-foreground ${
                    mono ? "font-mono text-sm break-all" : "break-words"
                }`}
            >
                {value || "-"}
            </span>
        </div>
    )
}

function StatBlock({ label, value }: { label: string; value: number }) {
    return (
        <div className="text-center p-4 bg-muted/50 rounded-lg">
            <div className="text-2xl font-bold text-foreground">
                {value.toLocaleString()}
            </div>
            <div className="text-xs text-muted-foreground mt-1">{label}</div>
        </div>
    )
}

type AgencyOverviewTabProps = {
    org: OrganizationDetail
    isDeleted: boolean
    purgeDate: Date | null
    restoreSubmitting: boolean
    deleteSubmitting: boolean
    purgeSubmitting: boolean
    onRestoreOrganization: () => void
    onDeleteOrganization: () => void
    onPurgeOrganization: () => void
}

export function AgencyOverviewTab({
    org,
    isDeleted,
    purgeDate,
    restoreSubmitting,
    deleteSubmitting,
    purgeSubmitting,
    onRestoreOrganization,
    onDeleteOrganization,
    onPurgeOrganization,
}: AgencyOverviewTabProps) {
    const [deleteOpen, setDeleteOpen] = useState(false)
    const [purgeOpen, setPurgeOpen] = useState(false)

    return (
        <div className="grid gap-6 md:grid-cols-2">
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Organization Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                    <DetailRow label="Name" value={org.name} />
                    <DetailRow label="Slug" value={org.slug} mono />
                    <DetailRow label="Timezone" value={org.timezone} />
                    <DetailRow label="Created" value={<UtcDate value={org.created_at} month="long" />} />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Statistics</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-4">
                    <StatBlock label="Members" value={org.member_count} />
                    <StatBlock label="Surrogates" value={org.surrogate_count} />
                    <StatBlock label="Active Matches" value={org.active_match_count} />
                    <StatBlock label="Tasks Pending" value={org.pending_task_count} />
                </CardContent>
            </Card>

            <Card className="md:col-span-2 border-destructive/30">
                <CardHeader>
                    <CardTitle className="text-lg text-destructive">Danger Zone</CardTitle>
                    <CardDescription>
                        Soft delete this organization for 30 days, then permanently remove all data.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {isDeleted ? (
                        <div className="space-y-3">
                            <div className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-900 dark:border-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-100">
                                Deletion scheduled
                                {purgeDate
                                    ? ` for ${format(purgeDate, "MMM d, yyyy h:mm a")}`
                                    : ""}
                                .
                            </div>
                            <Button
                                variant="outline"
                                onClick={onRestoreOrganization}
                                disabled={restoreSubmitting}
                            >
                                {restoreSubmitting ? (
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                ) : null}
                                Restore Organization
                            </Button>
                        </div>
                    ) : (
                        <div className="flex flex-wrap gap-2">
                            <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
                                <AlertDialogTrigger
                                    className={buttonVariants({ variant: "destructive-outline" })}
                                >
                                    Delete Organization
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                    <AlertDialogHeader>
                                        <AlertDialogTitle>Delete {org.name}?</AlertDialogTitle>
                                        <AlertDialogDescription>
                                            This will disable access immediately. Data will be permanently
                                            deleted after 30 days.
                                        </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                        <AlertDialogAction
                                            variant="destructive"
                                            onClick={onDeleteOrganization}
                                            disabled={deleteSubmitting}
                                        >
                                            {deleteSubmitting ? (
                                                <span className="inline-flex items-center gap-2">
                                                    <Loader2 className="size-4 animate-spin" />
                                                    Deleting
                                                </span>
                                            ) : (
                                                "Confirm Delete"
                                            )}
                                        </AlertDialogAction>
                                    </AlertDialogFooter>
                                </AlertDialogContent>
                            </AlertDialog>
                        </div>
                    )}

                    <div className="flex flex-wrap gap-2 border-t pt-4">
                        <AlertDialog open={purgeOpen} onOpenChange={setPurgeOpen}>
                            <AlertDialogTrigger
                                className={buttonVariants({ variant: "destructive" })}
                            >
                                Permanently delete now
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                                <AlertDialogHeader>
                                    <AlertDialogTitle>Permanently delete {org.name} now?</AlertDialogTitle>
                                    <AlertDialogDescription>
                                        This is irreversible and removes all organization data right away.
                                    </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                        variant="destructive"
                                        onClick={onPurgeOrganization}
                                        disabled={purgeSubmitting}
                                    >
                                        {purgeSubmitting ? (
                                            <span className="inline-flex items-center gap-2">
                                                <Loader2 className="size-4 animate-spin" />
                                                Deleting
                                            </span>
                                        ) : (
                                            "Delete now"
                                        )}
                                    </AlertDialogAction>
                                </AlertDialogFooter>
                            </AlertDialogContent>
                        </AlertDialog>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
