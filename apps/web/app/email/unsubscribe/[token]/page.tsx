import type { Metadata } from "next"
import { headers } from "next/headers"
import Link from "next/link"

export const dynamic = "force-dynamic"
export const metadata: Metadata = {
    title: "Email Unsubscribe",
    description: "Manage email subscription preferences.",
    robots: {
        index: false,
        follow: false,
    },
}

export default async function UnsubscribePage({
    params,
    searchParams,
}: {
    params: Promise<{ token: string }>
    searchParams?: Promise<{ status?: string | string[] }>
}) {
    const { token } = await params
    const resolvedSearchParams = searchParams ? await searchParams : {}
    const h = await headers()
    const orgName = h.get("x-org-name") || "Surrogacy Force"
    const status = Array.isArray(resolvedSearchParams.status)
        ? resolvedSearchParams.status[0]
        : resolvedSearchParams.status
    const isUnsubscribed = status === "unsubscribed"
    const confirmAction = `/email/unsubscribe/${encodeURIComponent(token)}/confirm`

    return (
        <main className="min-h-dvh bg-gradient-to-b from-background via-background to-muted/30 px-4 py-12">
            <div className="mx-auto w-full max-w-lg">
                <div className="mb-6">
                    <p className="text-xs font-medium tracking-wide text-muted-foreground">
                        Email Preferences
                    </p>
                    <h1 className="mt-2 text-2xl font-semibold leading-tight">
                        {isUnsubscribed ? "You're unsubscribed" : "Confirm unsubscribe"}
                    </h1>
                    <p className="mt-2 text-sm text-muted-foreground">
                        {isUnsubscribed ? (
                            <>
                                You will no longer receive marketing emails from{" "}
                                <span className="font-medium text-foreground">{orgName}</span>.
                            </>
                        ) : (
                            <>
                                Confirm that you want to stop receiving marketing emails from{" "}
                                <span className="font-medium text-foreground">{orgName}</span>.
                            </>
                        )}
                    </p>
                </div>

                <div className="rounded-xl border bg-card p-6 shadow-sm">
                    <div className="space-y-3 text-sm text-muted-foreground">
                        {isUnsubscribed ? (
                            <>
                                <p>
                                    If you still need to receive case-related updates, those may
                                    continue to be sent when required for service and account
                                    operations.
                                </p>
                                <p>
                                    If you unsubscribed by mistake, contact your agency to update
                                    your preferences.
                                </p>
                            </>
                        ) : (
                            <p>
                                This page does not change your subscription until you confirm.
                                Account and case-related service messages may still be sent when
                                required.
                            </p>
                        )}
                    </div>

                    <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        {isUnsubscribed ? (
                            <Link
                                href="/"
                                className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                            >
                                Return Home
                            </Link>
                        ) : (
                            <form action={confirmAction} method="post">
                                <button
                                    type="submit"
                                    className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                                >
                                    Unsubscribe
                                </button>
                            </form>
                        )}
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
