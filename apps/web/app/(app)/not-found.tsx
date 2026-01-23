import { NotFoundState } from "@/components/not-found-state"

/**
 * App group 404 page.
 *
 * Shown when navigating to a route that doesn't exist within the (app) group.
 * Links to /dashboard since we're in an authenticated context.
 */
export default function AppNotFound() {
    return <NotFoundState />
}
