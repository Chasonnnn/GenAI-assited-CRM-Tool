import { NotFoundState } from "@/components/error-state"

/** Renders inside the app shell for notFound() calls from authenticated routes. */
export default function AppNotFound() {
    return (
        <NotFoundState
            title="Page not found"
            backHref="/dashboard"
            backLabel="Go to Dashboard"
            headingLevel={1}
            className="min-h-[50vh]"
        />
    )
}
