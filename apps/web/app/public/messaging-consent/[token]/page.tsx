import { Button } from "@/components/ui/button"
import type { Metadata } from "next"
import { headers } from "next/headers"
import { randomUUID } from "node:crypto"

import { getMessagingPreference, type MessagingConsentStatus } from "./preference-api"

export const dynamic = "force-dynamic"
export const metadata: Metadata = {
    title: "Text Message Preferences",
    description: "Manage text message consent preferences.",
    robots: { index: false, follow: false },
}

const statusLabels: Record<MessagingConsentStatus, string> = {
    unknown: "Not enrolled",
    opted_in: "Enrolled",
    opted_out: "Opted out",
    reopt_pending: "Re-enrollment pending",
}

export default async function MessagingConsentPage({
    params,
    searchParams,
}: {
    params: Promise<{ token: string }>
    searchParams?: Promise<{ status?: string; error?: string }>
}) {
    const { token } = await params
    const query = searchParams ? await searchParams : {}
    const preference = await getMessagingPreference(token, await headers())

    if (!preference) {
        return (
            <main className="min-h-dvh bg-muted/30 px-4 py-16">
                <div className="mx-auto max-w-lg rounded-xl border bg-card p-6 shadow-sm">
                    <h1 className="text-2xl font-semibold">This link is unavailable</h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                        The text preference link is invalid or expired. Ask your agency for a new link.
                    </p>
                </div>
            </main>
        )
    }

    return (
        <main className="min-h-dvh bg-gradient-to-b from-background to-muted/30 px-4 py-12">
            <div className="mx-auto w-full max-w-2xl space-y-6">
                <header>
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Text message preferences
                    </p>
                    <h1 className="mt-2 text-2xl font-semibold">{preference.legal_brand}</h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                        Manage text messages sent to {preference.masked_phone}. Consent is optional and
                        is not a condition of applying or receiving services.
                    </p>
                </header>

                {query.status === "updated" ? (
                    <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
                        Your preference was recorded.
                    </div>
                ) : null}
                {query.error ? (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                        We could not update that preference. Request a new link or contact support.
                    </div>
                ) : null}

                {Object.entries(preference.purposes).map(([purpose, item]) => {
                    if (!item) return null
                    const title = purpose === "operational" ? "Application and process updates" : "Promotions and opportunities"
                    const pending = item.status === "reopt_pending"
                    const optInSubmissionId = randomUUID()
                    const optOutSubmissionId = randomUUID()
                    return (
                        <section key={purpose} className="rounded-xl border bg-card p-6 shadow-sm">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <h2 className="font-semibold">{title}</h2>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Current status: {statusLabels[item.status]}
                                    </p>
                                </div>
                            </div>
                            <p className="mt-4 text-sm leading-6 text-muted-foreground">{item.disclosure}</p>
                            {pending ? (
                                <p className="mt-3 text-sm text-amber-700">
                                    Messaging remains blocked until provider synchronization succeeds. If it
                                    cannot be completed, text START or UNSTOP to the corresponding number.
                                </p>
                            ) : null}
                            <div className="mt-5 flex flex-wrap gap-3">
                                <form action={`/public/messaging-consent/${encodeURIComponent(token)}/update`} method="post">
                                    <input type="hidden" name="action" value="opt_in" />
                                    <input type="hidden" name="purpose" value={purpose} />
                                    <input type="hidden" name="submission_id" value={optInSubmissionId} />
                                    <Button type="submit">Agree to these texts</Button>
                                </form>
                                <form action={`/public/messaging-consent/${encodeURIComponent(token)}/update`} method="post">
                                    <input type="hidden" name="action" value="opt_out" />
                                    <input type="hidden" name="purpose" value={purpose} />
                                    <input type="hidden" name="submission_id" value={optOutSubmissionId} />
                                    <Button type="submit" variant="outline">Stop these texts</Button>
                                </form>
                            </div>
                        </section>
                    )
                })}

                <footer className="space-y-2 text-xs text-muted-foreground">
                    <p>{preference.expected_frequency || "Message frequency varies."}</p>
                    <p>
                        Need help? {preference.support_contact}.{" "}
                        <a className="underline" href={preference.sms_terms_url}>SMS Terms</a>{" · "}
                        <a className="underline" href={preference.privacy_policy_url}>Privacy Policy</a>
                    </p>
                </footer>
            </div>
        </main>
    )
}
