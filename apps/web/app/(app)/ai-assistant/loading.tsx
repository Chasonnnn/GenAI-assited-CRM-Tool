import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function AIAssistantLoading() {
    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            <div className="flex items-center gap-3">
                <Skeleton className="h-8 w-8" />
                <div className="space-y-2">
                    <Skeleton className="h-6 w-32" />
                    <Skeleton className="h-4 w-64" />
                </div>
            </div>

            <div className="grid flex-1 gap-6 lg:grid-cols-[320px_1fr]">
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <Skeleton className="h-4 w-24" />
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {[...Array(4)].map((_, i) => (
                                <Skeleton key={i} className="h-10 w-full" />
                            ))}
                        </CardContent>
                    </Card>
                </div>

                <Card>
                    <CardHeader>
                        <Skeleton className="h-12 w-full" />
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Skeleton className="h-[400px] w-full" />
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
