import type { Metadata } from "next"

import AgenciesPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Agencies | SurrogacyForce Ops",
    description: "Browse and manage agency organizations in the SurrogacyForce operations console.",
}

export default function AgenciesPage() {
    return <AgenciesPageClient />
}
