import type { Metadata } from "next"
import { Suspense } from "react"
import PublicIntakeFormClient from "./page.client"

export const metadata: Metadata = {
    title: "Apply | Surrogacy Force",
    description: "Submit your intake application to join the Surrogacy Force program.",
}

function IntakePageFallback() {
    return (
        <div className="min-h-screen flex items-center justify-center p-4">
            <span className="text-sm text-stone-500">Loading intake form...</span>
        </div>
    )
}

type PageProps = {
    params: Promise<{ slug?: string | string[] }>
}

export default async function PublicIntakePage({ params }: PageProps) {
    const resolvedParams = await params

    const slugParam = resolvedParams.slug
    const slug = (Array.isArray(slugParam) ? slugParam[0] : slugParam) ?? ""

    return (
        <Suspense fallback={<IntakePageFallback />}>
            <PublicIntakeFormClient slug={slug} />
        </Suspense>
    )
}
