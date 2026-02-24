import type { Metadata } from "next"
import { notFound, redirect } from "next/navigation"

export const metadata: Metadata = {
    title: "Manage Appointment",
    description: "Redirecting to the appointment management page.",
}

interface PageProps {
    params: Promise<{ orgId?: string | string[]; token?: string | string[] }>
}

export default async function CancelRedirectPage({ params }: PageProps) {
    const resolvedParams = await params
    const rawOrgId = resolvedParams.orgId
    const rawToken = resolvedParams.token
    const orgId = Array.isArray(rawOrgId) ? rawOrgId[0] : rawOrgId
    const token = Array.isArray(rawToken) ? rawToken[0] : rawToken

    if (!orgId || !token) {
        notFound()
    }

    redirect(`/book/self-service/${orgId}/manage/${token}?action=cancel`)
}
