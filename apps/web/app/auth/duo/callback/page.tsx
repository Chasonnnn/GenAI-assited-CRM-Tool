import type { Metadata } from "next"

import DuoCallbackPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Duo verification | SurrogacyForce",
    description: "Complete Duo multi-factor authentication for SurrogacyForce.",
}

export default function DuoCallbackPage() {
    return <DuoCallbackPageClient />
}
