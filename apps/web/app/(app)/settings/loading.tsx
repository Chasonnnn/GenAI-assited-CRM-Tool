import { Card, CardContent } from "@/components/ui/card"

export default function SettingsLoading() {
    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-16 items-center px-6">
                    <div className="h-8 w-32 animate-pulse rounded bg-muted" />
                </div>
            </div>
            <div className="flex-1 p-6">
                <div className="flex gap-6">
                    <Card className="h-64 w-64 animate-pulse">
                        <CardContent className="p-4">
                            <div className="space-y-2">
                                <div className="h-10 rounded bg-muted" />
                                <div className="h-10 rounded bg-muted" />
                                <div className="h-10 rounded bg-muted" />
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="h-96 flex-1 animate-pulse">
                        <CardContent className="p-6">
                            <div className="space-y-4">
                                <div className="h-8 w-48 rounded bg-muted" />
                                <div className="h-4 w-96 rounded bg-muted" />
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
