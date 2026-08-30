import { Skeleton } from "@/components/ui/skeleton"

export default function DonorDetailLoading() {
    return (
        <div className="flex flex-1 flex-col gap-6 p-6" role="status" aria-label="Loading donor details">
            <div className="flex items-start justify-between gap-4">
                <div className="flex gap-4">
                    <Skeleton className="size-14 rounded-full" />
                    <div className="space-y-3">
                        <Skeleton className="h-8 w-64" />
                        <Skeleton className="h-5 w-48" />
                    </div>
                </div>
                <Skeleton className="h-9 w-64" />
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
                <Skeleton className="h-64 rounded-xl" />
                <Skeleton className="h-64 rounded-xl" />
            </div>
        </div>
    )
}
