import type { Metadata } from "next"

import OpsLoginPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Ops console login | SurrogacyForce",
    description: "Sign in to the SurrogacyForce operations console.",
}

export default function OpsLoginPage() {
    return <OpsLoginPageClient />
}
