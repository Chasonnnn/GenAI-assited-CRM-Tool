import { NotFoundState } from "@/components/error-state"

export default function RootNotFound() {
    return (
        <main className="flex min-h-dvh items-center justify-center">
            <NotFoundState title="Page not found" backHref="/" backLabel="Go home" headingLevel={1} />
        </main>
    )
}
