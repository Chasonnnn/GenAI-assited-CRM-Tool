import { NotFoundState } from "@/components/not-found-state"

/**
 * Global 404 page.
 *
 * Shown when navigating to a route that doesn't exist at the root level.
 * Links to /login since we're in a public context.
 */
export default function NotFound() {
    return (
        <NotFoundState
            title="Page not found"
            description="This page doesn't exist or you don't have access."
            primaryHref="/login"
            primaryLabel="Go to Login"
            fullHeight
        />
    )
}
