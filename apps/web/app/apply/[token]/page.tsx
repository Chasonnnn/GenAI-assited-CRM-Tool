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

type PageProps = {
    params: Promise<{ token?: string | string[] }>
    searchParams: Promise<{ formId?: string | string[] }>
}

export default async function PublicApplicationPage({ params, searchParams }: PageProps) {
    const resolvedParams = await params
    const resolvedSearchParams = await searchParams

    const tokenParam = resolvedParams.token
    const token = (Array.isArray(tokenParam) ? tokenParam[0] : tokenParam) ?? ""

    const formIdParam = resolvedSearchParams.formId
    const previewKey = (Array.isArray(formIdParam) ? formIdParam[0] : formIdParam) || "draft"

    return (
        <Suspense fallback={<ApplicationPageFallback />}>
            <PublicApplicationFormClient token={token} previewKey={previewKey} />
        </Suspense>
    )
}
