"use client"

import { useParams } from "next/navigation"
import { TabsContent } from "@/components/ui/tabs"
import { SurrogateHistoryTab } from "@/components/surrogates/detail/SurrogateHistoryTab"
import { useInfiniteSurrogateActivity } from "@/lib/hooks/use-surrogates"
import { formatDateTime } from "@/components/surrogates/detail/surrogate-detail-utils"

export default function SurrogateHistoryPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const activityQuery = useInfiniteSurrogateActivity(id)
    const activities = activityQuery.data?.pages.flatMap((page) => page.items) ?? []
    const initialLoadError = activityQuery.isError && activities.length === 0

    return (
        <TabsContent value="history" className="space-y-4">
            <SurrogateHistoryTab
                activities={activities}
                formatDateTime={formatDateTime}
                status={activityQuery.isLoading ? "loading" : initialLoadError ? "error" : "ready"}
                onRetry={() => { void activityQuery.refetch() }}
                hasMore={activityQuery.hasNextPage}
                isLoadingMore={activityQuery.isFetchingNextPage}
                loadMoreError={activityQuery.isFetchNextPageError}
                onLoadMore={() => { void activityQuery.fetchNextPage() }}
            />
        </TabsContent>
    )
}
