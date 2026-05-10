import type { Metadata } from "next"

import PlatformSystemEmailTemplateNewPage from "./page.client"

export const metadata: Metadata = {
    title: "New system email template | SurrogacyForce Ops",
    description: "Create a platform-managed system email template.",
}

export default function Page() {
    return <PlatformSystemEmailTemplateNewPage />
}
