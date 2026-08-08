import { LoadingShell } from "@/components/loading-shell"

export default function MatchesLoading() {
    return (
        <div role="status" aria-label="Loading matches">
            <span className="sr-only">Loading matches</span>
            <div aria-hidden="true">
                <LoadingShell variant="cards" />
            </div>
        </div>
    )
}
