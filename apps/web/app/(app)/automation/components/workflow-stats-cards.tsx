import { TrendingUpIcon } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { WorkflowStats } from "@/lib/api/workflows"

export function WorkflowStatsCards({
    stats,
    isLoading,
}: {
    stats: WorkflowStats | undefined
    isLoading: boolean
}) {
    return (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total Workflows</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {isLoading ? "-" : stats?.total_workflows ?? 0}
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Enabled</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {isLoading ? "-" : stats?.enabled_workflows ?? 0}
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Success Rate 24h</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-baseline gap-2">
                        <div className="text-2xl font-bold">
                            {isLoading ? "-" : `${stats?.success_rate_24h?.toFixed(1) ?? 0}%`}
                        </div>
                        {stats?.success_rate_24h && stats.success_rate_24h > 95 && (
                            <div className="flex items-center text-xs font-medium text-green-600">
                                <TrendingUpIcon className="mr-1 size-3" />
                                Good
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Executions 24h</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {isLoading ? "-" : stats?.total_executions_24h ?? 0}
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
