import type { Metadata } from "next"

import OrganizationEmailTemplateStudio from "@/components/email/organization-email-template-studio"

export const metadata: Metadata = {
    title: "New personal email template | SurrogacyForce",
    description:
        "Create, test, and publish a personal email template without changing production content.",
}

export default function NewPersonalEmailTemplatePage() {
    return <OrganizationEmailTemplateStudio scope="personal" />
}
