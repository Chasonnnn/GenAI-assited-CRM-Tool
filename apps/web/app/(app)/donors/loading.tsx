import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function DonorsLoading() {
    return (
        <div className="flex h-full flex-col" role="status" aria-label="Loading donors">
            <div className="flex h-16 items-center border-b px-6">
                <Skeleton className="h-8 w-32" />
            </div>
            <div className="flex-1 space-y-6 p-6">
                <Skeleton className="h-9 w-64" />
                <div className="flex justify-between gap-4">
                    <Skeleton className="h-10 w-44" />
                    <Skeleton className="h-10 w-full max-w-sm" />
                </div>
                <Card className="p-6"><Skeleton className="h-96 w-full" /></Card>
            </div>
        </div>
    )
}
