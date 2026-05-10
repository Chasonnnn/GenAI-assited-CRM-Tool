import type { Metadata } from "next"

import OpsAlertsPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Platform alerts | SurrogacyForce Ops",
    description: "Review and resolve SurrogacyForce platform alerts.",
}

export default function OpsAlertsPage() {
    return <OpsAlertsPageClient />
}
