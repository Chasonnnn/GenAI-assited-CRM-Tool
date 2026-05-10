import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

const AUTOMATION_LOADING_CARD_IDS = [
    "workflow-library",
    "active-campaigns",
    "email-templates",
    "form-builder",
    "execution-health",
    "recent-runs",
] as const

export default function AutomationLoading() {
    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <Skeleton className="h-8 w-32" />
                    <Skeleton className="h-10 w-40" />
                </div>
            </div>

            <div className="flex-1 space-y-4 p-6">
                <Skeleton className="h-10 w-64" />
                {AUTOMATION_LOADING_CARD_IDS.map((skeletonId) => (
                    <Card key={skeletonId}>
                        <CardContent className="flex items-center justify-between p-6">
                            <div className="flex items-start gap-4">
                                <Skeleton className="size-12" />
                                <div className="space-y-2">
                                    <Skeleton className="h-5 w-48" />
                                    <Skeleton className="h-4 w-72" />
                                    <Skeleton className="h-5 w-32" />
                                </div>
                            </div>
                            <Skeleton className="h-6 w-12" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
