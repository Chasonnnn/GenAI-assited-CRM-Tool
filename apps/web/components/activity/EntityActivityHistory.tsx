"use client"

import { ArrowLeftIcon, Loader2Icon } from "lucide-react"

import Link from "@/components/app-link"
import { ActivityEventRow } from "@/components/activity/EntityActivityTimeline"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ActivityEntityType } from "@/lib/api/activity"
import { useInfiniteEntityActivity } from "@/lib/hooks/use-entity-activity"

export function EntityActivityHistory({
    entityType,
    entityId,
    backHref,
}: {
    entityType: ActivityEntityType
    entityId: string
    backHref: string
}) {
    const query = useInfiniteEntityActivity(entityType, entityId)
    const activities = query.data?.pages.flatMap((page) => page.items) ?? []
    const initialLoadError = query.isError && activities.length === 0

    return (
        <div className="flex flex-1 flex-col">
            <header className="flex min-h-16 items-center gap-3 border-b px-6">
                <Link
                    href={backHref}
                    aria-label="Back to details"
                    className="inline-flex size-9 items-center justify-center rounded-md border border-input hover:bg-accent"
                >
                    <ArrowLeftIcon className="size-4" />
                </Link>
                <h1 className="text-xl font-semibold">Activity history</h1>
            </header>
            <main className="mx-auto w-full max-w-4xl p-6">
                <Card>
                    <CardHeader><CardTitle><h2>Activity</h2></CardTitle></CardHeader>
                    <CardContent>
                        {query.isLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading activity…
                            </div>
                        ) : initialLoadError ? (
                            <div className="space-y-3">
                                <p className="text-sm text-destructive">Failed to load activity.</p>
                                <Button variant="outline" size="sm" onClick={() => { void query.refetch() }}>
                                    Retry
                                </Button>
                            </div>
                        ) : activities.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No activity yet.</p>
                        ) : (
                            <ol className="divide-y" aria-label="Activity history entries">
                                {activities.map((activity) => (
                                    <li key={`${activity.activity_type}:${activity.id}`}>
                                        <ActivityEventRow
                                            activity={activity}
                                            showExactTimestamp
                                        />
                                    </li>
                                ))}
                            </ol>
                        )}
                        {activities.length > 0 && query.isFetchNextPageError ? (
                            <p className="mt-4 text-sm text-destructive" role="alert">
                                Failed to load more activity.
                            </p>
                        ) : null}
                        {query.hasNextPage ? (
                            <Button
                                variant="outline"
                                className="mt-4 w-full"
                                disabled={query.isFetchingNextPage}
                                onClick={() => { void query.fetchNextPage() }}
                            >
                                {query.isFetchingNextPage
                                    ? "Loading…"
                                    : query.isFetchNextPageError
                                      ? "Retry load more"
                                      : "Load more"}
                            </Button>
                        ) : null}
                    </CardContent>
                </Card>
            </main>
        </div>
    )
}
