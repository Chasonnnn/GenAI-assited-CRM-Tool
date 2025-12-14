import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function ReportsLoading() {
    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <Skeleton className="h-8 w-24" />
                    <Skeleton className="h-10 w-24" />
                </div>
            </div>

            <div className="flex-1 space-y-6 p-6">
                <div className="grid gap-6 md:grid-cols-2">
                    {[...Array(4)].map((_, i) => (
                        <Card key={i}>
                            <CardHeader>
                                <Skeleton className="h-6 w-32" />
                            </CardHeader>
                            <CardContent>
                                <Skeleton className="h-[300px] w-full" />
                            </CardContent>
                            <CardFooter>
                                <Skeleton className="h-4 w-20" />
                            </CardFooter>
                        </Card>
                    ))}
                </div>

                <div className="grid gap-4 md:grid-cols-4">
                    {[...Array(4)].map((_, i) => (
                        <Card key={i}>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <Skeleton className="h-4 w-24" />
                                <Skeleton className="size-4" />
                            </CardHeader>
                            <CardContent>
                                <Skeleton className="h-8 w-16 mb-2" />
                                <Skeleton className="h-3 w-32" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    )
}
