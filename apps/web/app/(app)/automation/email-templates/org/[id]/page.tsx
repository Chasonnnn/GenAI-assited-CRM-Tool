import type { Metadata } from "next"

import OrganizationEmailTemplateStudio from "@/components/email/organization-email-template-studio"

export const metadata: Metadata = {
    title: "Organization email template | SurrogacyForce",
    description:
        "Edit, test, and explicitly publish an organization email template draft.",
}

type PageProps = {
    params: Promise<{ id: string }>
}

export default async function OrganizationEmailTemplateDetailPage({
    params,
}: PageProps) {
    const { id } = await params
    return <OrganizationEmailTemplateStudio templateId={id} />
}
