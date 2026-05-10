import type { Metadata } from "next"

import TemplatesStudioPageClient from "./page.client"

export const metadata: Metadata = {
    title: "Template studio | SurrogacyForce Ops",
    description: "Manage platform email, form, workflow, and system templates.",
}

export default function TemplatesStudioPage() {
    return <TemplatesStudioPageClient />
}
