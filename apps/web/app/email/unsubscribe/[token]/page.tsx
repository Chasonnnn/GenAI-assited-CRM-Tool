import { headers } from "next/headers"
import Link from "next/link"

export const dynamic = "force-dynamic"

async function _processUnsubscribe(token: string) {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
    const safeToken = encodeURIComponent(token || "")
    if (!safeToken) return

    // Best-effort: the API endpoint is the source of truth for recording suppressions.
    // We intentionally show the same success message regardless of token validity.
    try {
        await fetch(`${apiBase}/email/unsubscribe/${safeToken}`, {
            method: "POST",
            // No cookies required; token is the auth.
            cache: "no-store",
        })
    } catch {
        // Ignore failures to avoid leaking availability details to recipients.
    }
}

export default async function UnsubscribePage({
    params,
}: {
    params: Promise<{ token: string }>
}) {
    const { token } = await params
    const h = await headers()
    const orgName = h.get("x-org-name") || "Surrogacy Force"

    await _processUnsubscribe(token)

    return (
        <main className="min-h-dvh bg-gradient-to-b from-background via-background to-muted/30 px-4 py-12">
            <div className="mx-auto w-full max-w-lg">
                <div className="mb-6">
                    <p className="text-xs font-medium tracking-wide text-muted-foreground">
                        Email Preferences
                    </p>
                    <h1 className="mt-2 text-2xl font-semibold leading-tight">
                        You&apos;re unsubscribed
                    </h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                        You will no longer receive marketing emails from{" "}
                        <span className="font-medium text-foreground">{orgName}</span>.
                    </p>
                </div>

                <div className="rounded-xl border bg-card p-6 shadow-sm">
                    <div className="space-y-3 text-sm text-muted-foreground">
                        <p>
                            If you still need to receive case-related updates, those may continue to
                            be sent when required for service and account operations.
                        </p>
                        <p>
                            If you unsubscribed by mistake, contact your agency to update your
                            preferences.
                        </p>
                    </div>

                    <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <Link
                            href="/"
                            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                        >
                            Return Home
                        </Link>
                        <Link
                            href="/"
                            className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
                        >
                            surrogacyforce.com
                        </Link>
                    </div>
                </div>
            </div>
        </main>
    )
}
