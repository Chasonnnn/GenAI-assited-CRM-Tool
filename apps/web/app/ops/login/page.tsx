import type { Metadata } from "next"

import OpsLoginPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Ops console login | SurrogacyForce",
    description: "Sign in to the SurrogacyForce operations console.",
}

type PageProps = {
    searchParams: Promise<Record<string, string | string[] | undefined>>
}

// The ops layout reaches this page with router.replace, which updates window.location only after
// the new page renders, so the error code comes from the route's searchParams.
export default async function OpsLoginPage({ searchParams }: PageProps) {
    const { error } = await searchParams
    const errorCode = Array.isArray(error) ? error[0] : error
    return <OpsLoginPageClient errorCode={errorCode ?? null} />
}
