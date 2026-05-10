import type { Metadata } from "next"

import AgencyDetailPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Agency detail | SurrogacyForce Ops",
    description: "Review and manage an agency in the SurrogacyForce operations console.",
}

export default function AgencyDetailPage() {
    return <AgencyDetailPageClient />
}
