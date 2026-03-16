import { notFound } from "next/navigation"

import FormBuilderPageClient from "./page.client"
import { getServerRouteResourceStatus } from "@/lib/server-route-resource"

type PageProps = {
    params: Promise<{ id?: string | string[] }>
}

export default async function FormBuilderPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawId = resolvedParams.id
    const formId = Array.isArray(rawId) ? rawId[0] : rawId

    if (!formId) {
        notFound()
    }
    if (formId === "new") {
        return <FormBuilderPageClient />
    }

    const status = await getServerRouteResourceStatus(
        `/forms/${encodeURIComponent(formId)}`,
    )
    if (status === "not_found") {
        notFound()
    }

    return <FormBuilderPageClient />
}
