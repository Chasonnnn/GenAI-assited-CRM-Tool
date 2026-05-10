import type { Metadata } from "next"

import MFAPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Multi-factor authentication | SurrogacyForce",
    description: "Verify your identity before continuing to SurrogacyForce.",
}

export default function MFAPage() {
    return <MFAPageClient />
}
