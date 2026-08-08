import { LoadingShell } from "@/components/loading-shell"

export default function MatchDetailLoading() {
    return (
        <div role="status" aria-label="Loading match details">
            <span className="sr-only">Loading match details</span>
            <div aria-hidden="true">
                <LoadingShell variant="profile" />
            </div>
        </div>
    )
}
