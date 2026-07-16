import type { Metadata } from "next"

import EmbedFormPageClient from "./page.client"

export const dynamic = "force-dynamic"
export const revalidate = 0
export const fetchCache = "force-no-store"

export const metadata: Metadata = {
    title: "Secure intake form | SurrogacyForce",
    description: "Complete a secure SurrogacyForce intake form.",
}

type PageProps = {
    params: Promise<{ slug: string }>
    searchParams: Promise<{ parent_origin?: string | string[] }>
}

export default async function EmbedFormPage({ params, searchParams }: PageProps) {
    const { slug } = await params
    const { parent_origin: rawParentOrigin } = await searchParams
    const initialParentOrigin = Array.isArray(rawParentOrigin)
        ? rawParentOrigin[0] ?? null
        : rawParentOrigin ?? null

    return (
        <EmbedFormPageClient
            slug={slug}
            initialParentOrigin={initialParentOrigin}
        />
    )
}
