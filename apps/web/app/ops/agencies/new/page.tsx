import type { Metadata } from "next"

import NewAgencyPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Create agency | SurrogacyForce Ops",
    description: "Create a new agency organization in the SurrogacyForce operations console.",
}

export default function NewAgencyPage() {
    return <NewAgencyPageClient />
}
