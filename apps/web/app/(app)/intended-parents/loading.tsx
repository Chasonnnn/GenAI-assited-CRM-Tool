import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-10 w-48" />
                </div>
            </div>

            <div className="flex-1 space-y-4 p-6">
                <div className="flex flex-wrap items-center gap-3">
                    <Skeleton className="h-10 w-[180px]" />
                    <Skeleton className="ml-auto h-10 w-full max-w-sm" />
                </div>

                <Card className="overflow-hidden">
                    <div className="p-6">
                        <Skeleton className="h-[400px] w-full" />
                    </div>
                </Card>
            </div>
        </div>
    )
}
