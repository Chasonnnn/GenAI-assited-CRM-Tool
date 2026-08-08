export default function IntendedParentDetailLoading() {
    return (
        <div
            role="status"
            aria-label="Loading intended parent details"
            className="flex flex-1 flex-col gap-6 p-6"
        >
            <span className="sr-only">Loading intended parent details</span>
            <div className="animate-pulse space-y-6" aria-hidden="true">
                <div className="flex items-start justify-between gap-4">
                    <div className="space-y-3">
                        <div className="h-8 w-64 rounded-md bg-muted" />
                        <div className="h-5 w-36 rounded-full bg-muted/80" />
                    </div>
                    <div className="h-9 w-28 rounded-md bg-muted" />
                </div>
                <div className="grid gap-6 lg:grid-cols-2">
                    <div className="h-72 rounded-xl border bg-card" />
                    <div className="h-72 rounded-xl border bg-card" />
                    <div className="h-56 rounded-xl border bg-card" />
                    <div className="h-56 rounded-xl border bg-card" />
                </div>
            </div>
        </div>
    )
}
