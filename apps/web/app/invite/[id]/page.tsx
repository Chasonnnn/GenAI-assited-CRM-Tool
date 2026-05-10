import type { Metadata } from "next"

import InviteAcceptPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Accept invitation | SurrogacyForce",
    description: "Review and accept your SurrogacyForce organization invitation.",
}

export default function InviteAcceptPage() {
    return <InviteAcceptPageClient />
}
