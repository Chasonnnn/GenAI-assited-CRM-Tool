import type { Metadata } from "next"

import OpsDashboardPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Operations dashboard | SurrogacyForce Ops",
    description: "Monitor SurrogacyForce platform operations, agencies, users, and alerts.",
}

export default function OpsDashboardPage() {
    return <OpsDashboardPageClient />
}
