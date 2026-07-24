import type { Metadata } from "next"

import OrganizationEmailTemplateStudio from "@/components/email/organization-email-template-studio"

export const metadata: Metadata = {
    title: "New organization email template | SurrogacyForce",
    description:
        "Create, test, and publish an organization email template without changing production content.",
}

export default function NewOrganizationEmailTemplatePage() {
    return <OrganizationEmailTemplateStudio />
}
