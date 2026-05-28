import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = {
    title: "Privacy Policy | Surrogacy Force",
    description: "How Surrogacy Force collects, uses, protects, and shares personal data.",
    robots: {
        index: true,
        follow: true,
    },
}

const lastUpdated = "May 22, 2026"

export default function PrivacyPage() {
    return (
        <main className="min-h-screen bg-zinc-50 text-zinc-900">
            <div className="mx-auto max-w-3xl px-5 py-12 sm:py-16">
                <header className="mb-10 border-b border-zinc-200 pb-8">
                    <Link
                        href="/"
                        className="text-sm font-medium text-zinc-500 hover:text-zinc-900"
                    >
                        Surrogacy Force
                    </Link>
                    <h1 className="mt-6 text-4xl font-semibold tracking-normal text-zinc-950">
                        Privacy Policy
                    </h1>
                    <p className="mt-3 text-sm text-zinc-500">Last updated: {lastUpdated}</p>
                </header>

                <div className="space-y-10 text-sm leading-7 text-zinc-700">
                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Overview</h2>
                        <p>
                            Surrogacy Force is a case management and operations platform for
                            surrogacy agency teams. This policy explains how Surrogacy Force
                            collects, uses, stores, and shares information when users sign in,
                            manage client records, use intake or booking pages, and connect
                            third-party integrations such as Google Calendar, Gmail, Google Tasks,
                            Google Meet, and Duo.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            Information we collect
                        </h2>
                        <p>
                            We collect account information such as name, email address, role,
                            organization membership, authentication status, and security settings.
                            Agency users may enter or receive operational information such as
                            surrogate and intended parent records, notes, tasks, appointment
                            details, intake form responses, attachments, message metadata, and
                            audit history.
                        </p>
                        <p>
                            Public intake and booking pages may collect information submitted by
                            the person completing the form, including contact information,
                            appointment preferences, and form responses needed by the agency that
                            uses Surrogacy Force.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            How we use information
                        </h2>
                        <p>
                            We use information to provide the CRM, authenticate users, enforce
                            organization access controls, schedule and manage appointments, process
                            intake forms, send notifications, maintain audit logs, troubleshoot
                            issues, prevent abuse, and support agency workflows requested by the
                            organization using Surrogacy Force.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Google user data</h2>
                        <p>
                            When a user connects a Google account, Surrogacy Force may receive the
                            Google account email address, OAuth tokens, granted scopes, calendar
                            metadata, calendar event details, Google Meet conference details, Gmail
                            message metadata or content needed for connected email features, and
                            Google Tasks data when those integrations are enabled by the user or
                            their organization.
                        </p>
                        <p>
                            Surrogacy Force uses Google user data only to provide user-facing
                            connected features: signing in with Google, showing connection status,
                            syncing appointment availability, creating, updating, and cancelling
                            calendar events, adding Google Meet links, processing Google calendar
                            webhooks, supporting connected email workflows, and syncing tasks or
                            reminders when enabled.
                        </p>
                        <p>
                            Surrogacy Force does not sell Google user data, use it for advertising,
                            transfer it to data brokers, or use it to determine creditworthiness.
                            Surrogacy Force does not use Google Workspace API data to train,
                            develop, or improve generalized artificial intelligence or machine
                            learning models.
                        </p>
                        <p>
                            Surrogacy Force&apos;s use and transfer of information received from Google
                            APIs adheres to the{" "}
                            <a
                                href="https://developers.google.com/terms/api-services-user-data-policy"
                                className="font-medium text-zinc-950 underline underline-offset-4"
                            >
                                Google API Services User Data Policy
                            </a>
                            , including the Limited Use requirements.
                        </p>
                        <p>
                            We do not allow humans to read Google user data except when necessary
                            to provide support requested by the user or organization, investigate
                            abuse or security issues, comply with law, or operate the service in an
                            aggregated or de-identified form.
                        </p>
                        <p>
                            Users can disconnect Google integrations in Surrogacy Force settings or
                            revoke access from their Google Account permissions page. After access is
                            revoked, Surrogacy Force stops receiving new Google user data from that
                            account unless the user reconnects it.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Sharing</h2>
                        <p>
                            We share information only as needed to provide and secure Surrogacy
                            Force, including with infrastructure, authentication, email, calendar,
                            storage, logging, and support providers. We may also share information
                            when directed by the organization using the service, with the user's
                            consent, as required by law, or as part of a merger, acquisition, or
                            sale of assets with appropriate notice.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Security</h2>
                        <p>
                            We use administrative, technical, and organizational safeguards designed
                            to protect information in transit and at rest. Access is limited by
                            organization membership, role permissions, authentication controls, and
                            audit logging. No method of transmission or storage is completely secure,
                            so we continue to monitor and improve safeguards over time.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Retention</h2>
                        <p>
                            We retain information for as long as needed to provide Surrogacy Force,
                            comply with legal obligations, resolve disputes, enforce agreements,
                            maintain security, and support agency recordkeeping. Organizations may
                            request deletion or export of data according to their service
                            relationship and applicable law.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Your choices</h2>
                        <p>
                            Agency users can update account information through their organization,
                            disconnect integrations, request deletion where available, and revoke
                            Google access in their Google Account. People who submit intake forms or
                            booking requests should contact the agency that collected their
                            information for record access, correction, or deletion requests.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Contact</h2>
                        <p>
                            For privacy questions about Surrogacy Force, contact your organization
                            administrator or email{" "}
                            <a
                                href="mailto:privacy@surrogacyforce.com"
                                className="font-medium text-zinc-950 underline underline-offset-4"
                            >
                                privacy@surrogacyforce.com
                            </a>
                            . If you submitted information through an agency's public form or
                            booking page, contact that agency directly for requests about your
                            records.
                        </p>
                    </section>
                </div>

                <footer className="mt-12 border-t border-zinc-200 pt-6 text-sm text-zinc-500">
                    <Link href="/terms" className="font-medium text-zinc-900 underline underline-offset-4">
                        Terms of Service
                    </Link>
                </footer>
            </div>
        </main>
    )
}
