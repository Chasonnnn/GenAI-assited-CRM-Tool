import type { Metadata } from "next"

import PlatformSystemEmailTemplatePageClient from "./page.client"

export async function generateMetadata({
    params,
}: {
    params: Promise<{ systemKey: string }>
}): Promise<Metadata> {
    const { systemKey } = await params
    return {
        title: `${systemKey} system email template | SurrogacyForce Ops`,
        description: "Manage a platform-managed system email template.",
    }
}

export default function Page() {
    return <PlatformSystemEmailTemplatePageClient />
}
