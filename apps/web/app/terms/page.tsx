import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = {
    title: "Terms of Service | Surrogacy Force",
    description: "Terms governing access to and use of Surrogacy Force.",
    robots: {
        index: true,
        follow: true,
    },
}

const lastUpdated = "May 22, 2026"

export default function TermsPage() {
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
                        Terms of Service
                    </h1>
                    <p className="mt-3 text-sm text-zinc-500">Last updated: {lastUpdated}</p>
                </header>

                <div className="space-y-10 text-sm leading-7 text-zinc-700">
                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Agreement</h2>
                        <p>
                            These Terms of Service govern access to and use of Surrogacy Force, a
                            private CRM and operations platform for surrogacy agency teams. By using
                            Surrogacy Force, you agree to these terms on behalf of yourself and, if
                            applicable, the organization you represent.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Use of the service</h2>
                        <p>
                            Surrogacy Force may be used only by authorized users for legitimate
                            agency operations, including intake, case management, appointment
                            scheduling, records coordination, communications, and related workflows.
                            Users are responsible for maintaining accurate account information,
                            protecting credentials, and using the service in compliance with
                            applicable laws and organizational policies.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            Accounts and access
                        </h2>
                        <p>
                            Access may require Google sign-in, multifactor authentication, and
                            organization membership. Administrators control user invitations, roles,
                            permissions, and organization data. You must not share credentials,
                            bypass access controls, or access data outside your authorized
                            organization.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Customer data</h2>
                        <p>
                            Organizations and their users are responsible for the records, files,
                            messages, form responses, and other data they submit to Surrogacy Force.
                            Surrogacy Force processes that data to provide and secure the service,
                            support requested workflows, troubleshoot issues, and comply with legal
                            obligations.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            Third-party integrations
                        </h2>
                        <p>
                            Surrogacy Force may connect to third-party services such as Google
                            Calendar, Gmail, Google Tasks, Google Meet, email providers, messaging
                            services, and authentication providers. Use of those integrations may be
                            subject to third-party terms and permission settings. Users can revoke
                            connected access where supported by the third-party provider or in
                            Surrogacy Force settings.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            Acceptable use
                        </h2>
                        <p>
                            You may not use Surrogacy Force to violate law, infringe rights, upload
                            malicious code, interfere with service operation, attempt unauthorized
                            access, scrape or reverse engineer the service, send unlawful messages,
                            or process data you are not authorized to process.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            No professional advice
                        </h2>
                        <p>
                            Surrogacy Force is an operational software tool. It does not provide
                            medical, legal, financial, or clinical advice. Organizations remain
                            responsible for professional judgment, required consents, compliance
                            obligations, and decisions made using information managed in the service.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Privacy</h2>
                        <p>
                            Our{" "}
                            <Link
                                href="/privacy"
                                className="font-medium text-zinc-950 underline underline-offset-4"
                            >
                                Privacy Policy
                            </Link>{" "}
                            explains how Surrogacy Force collects, uses, protects, and shares
                            information, including information received through Google integrations.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            Availability and changes
                        </h2>
                        <p>
                            We may update, suspend, or discontinue parts of the service as needed to
                            operate, improve, secure, or comply with legal requirements. We may also
                            update these terms from time to time. Continued use after an update
                            means you accept the updated terms.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">
                            Disclaimers and limitations
                        </h2>
                        <p>
                            Surrogacy Force is provided on an as-is and as-available basis to the
                            maximum extent permitted by law. We are not liable for indirect,
                            incidental, consequential, special, exemplary, or punitive damages, or
                            for loss of profits, revenue, goodwill, or data, except where such
                            limitations are not permitted by law.
                        </p>
                    </section>

                    <section className="space-y-3">
                        <h2 className="text-xl font-semibold text-zinc-950">Contact</h2>
                        <p>
                            For questions about these terms, email{" "}
                            <a
                                href="mailto:privacy@surrogacyforce.com"
                                className="font-medium text-zinc-950 underline underline-offset-4"
                            >
                                privacy@surrogacyforce.com
                            </a>
                            .
                        </p>
                    </section>
                </div>
            </div>
        </main>
    )
}
