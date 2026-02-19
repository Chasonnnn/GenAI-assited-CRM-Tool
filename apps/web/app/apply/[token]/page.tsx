import type { Metadata } from "next"
import { Suspense } from "react"
import PublicApplicationFormClient from "./page.client"

export const metadata: Metadata = {
    title: "Apply | Surrogacy Force",
    description: "Submit your application to join the Surrogacy Force program.",
}

function ApplicationPageFallback() {
    return (
        <div className="min-h-screen flex items-center justify-center p-4">
            <span className="text-sm text-stone-500">Loading application...</span>
        </div>
    )
}

export default function PublicApplicationPage() {
    return (
        <Suspense fallback={<ApplicationPageFallback />}>
            <PublicApplicationFormClient />
        </Suspense>
    )
}
