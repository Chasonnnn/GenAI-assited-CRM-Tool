import type { Metadata } from "next"
import Link from "next/link"
import {
    ArrowRightIcon,
    CalendarDaysIcon,
    CheckCircle2Icon,
    ShieldCheckIcon,
} from "lucide-react"

export const metadata: Metadata = {
    title: "Surrogacy Force | Private CRM for surrogacy teams",
    description:
        "A private CRM for surrogacy teams to manage intake, appointments, records, and follow-up.",
    robots: {
        index: true,
        follow: true,
    },
}

export default function RootPage() {
    return (
        <main className="min-h-screen overflow-hidden bg-[#f7f4ee] text-[#1f2521]">
            <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-5 py-5 sm:px-8 lg:px-10">
                <header className="flex items-center justify-between border-b border-[#ded7cb] pb-5">
                    <Link href="/" className="text-base font-semibold tracking-normal text-[#1f2521]">
                        Surrogacy Force
                    </Link>
                    <nav className="flex items-center gap-5 text-sm text-[#6e6a61]">
                        <Link href="/privacy" className="transition hover:text-[#1f2521]">
                            Privacy
                        </Link>
                        <Link href="/terms" className="transition hover:text-[#1f2521]">
                            Terms
                        </Link>
                    </nav>
                </header>

                <section className="grid flex-1 items-center gap-12 py-14 lg:grid-cols-[0.95fr_1.05fr] lg:py-10">
                    <div className="max-w-2xl">
                        <h1 className="max-w-3xl text-5xl font-semibold leading-[1.02] tracking-normal text-[#18201c] sm:text-6xl lg:text-7xl">
                            Surrogacy Force
                        </h1>
                        <p className="mt-6 max-w-2xl text-3xl font-semibold leading-tight tracking-normal text-[#18201c] sm:text-4xl">
                            Run every journey from one trusted workspace.
                        </p>
                        <p className="mt-7 max-w-xl text-lg leading-8 text-[#5f5b52]">
                            A private CRM for surrogacy teams to manage intake, appointments,
                            records, and follow-up with less operational drag.
                        </p>
                        <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                            <Link
                                href="/login"
                                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-[#193b32] px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-[#102a23]"
                            >
                                Sign in
                                <ArrowRightIcon className="size-4" aria-hidden="true" />
                            </Link>
                            <p className="text-sm text-[#7b766d]">
                                Built for private agency operations.
                            </p>
                        </div>
                    </div>

                    <div className="relative min-h-[420px] lg:min-h-[560px]" aria-hidden="true">
                        <div className="absolute inset-x-4 top-10 h-[82%] rounded-[2rem] border border-[#d8cfc1] bg-[#efe8dd] shadow-[0_40px_90px_rgba(48,39,28,0.16)] lg:inset-x-0" />
                        <div className="absolute left-0 right-0 top-0 mx-auto max-w-[610px] rounded-[1.6rem] border border-[#d5ccbf] bg-[#fffaf2] p-4 shadow-[0_28px_70px_rgba(48,39,28,0.18)]">
                            <div className="flex items-center justify-between border-b border-[#ebe3d6] px-2 pb-4">
                                <div>
                                    <div className="text-sm font-semibold text-[#1f2521]">
                                        Intake workspace
                                    </div>
                                    <div className="mt-1 text-xs text-[#8a8478]">
                                        Today&apos;s appointments and follow-up
                                    </div>
                                </div>
                                <div className="rounded-full bg-[#dce8df] px-3 py-1 text-xs font-medium text-[#244d40]">
                                    Synced
                                </div>
                            </div>

                            <div className="grid gap-4 pt-4 sm:grid-cols-[1.05fr_0.95fr]">
                                <div className="space-y-3">
                                    {[
                                        ["New inquiry", "Review intake form"],
                                        ["Consult scheduled", "Google Meet ready"],
                                        ["Records updated", "Follow-up assigned"],
                                    ].map(([title, detail]) => (
                                        <div
                                            key={title}
                                            className="rounded-2xl border border-[#ebe3d6] bg-white px-4 py-3"
                                        >
                                            <div className="flex items-center gap-3">
                                                <CheckCircle2Icon className="size-4 text-[#2d6b59]" />
                                                <div>
                                                    <div className="text-sm font-medium text-[#242821]">
                                                        {title}
                                                    </div>
                                                    <div className="text-xs text-[#817b70]">{detail}</div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="rounded-2xl border border-[#ebe3d6] bg-[#f6f1e9] p-4">
                                    <div className="flex items-center gap-2 text-sm font-medium text-[#242821]">
                                        <CalendarDaysIcon className="size-4 text-[#2d6b59]" />
                                        Calendar
                                    </div>
                                    <div className="mt-5 space-y-3">
                                        <div className="rounded-xl bg-white px-3 py-3">
                                            <div className="text-xs text-[#8a8478]">11:30 AM</div>
                                            <div className="mt-1 text-sm font-medium text-[#242821]">
                                                Initial interview
                                            </div>
                                        </div>
                                        <div className="rounded-xl bg-[#193b32] px-3 py-3 text-white">
                                            <div className="text-xs text-white/70">2:00 PM</div>
                                            <div className="mt-1 text-sm font-medium">
                                                Case review
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="absolute bottom-4 left-8 hidden w-56 rounded-2xl border border-[#d8cfc1] bg-white/90 p-4 shadow-[0_20px_50px_rgba(48,39,28,0.12)] backdrop-blur sm:block">
                            <div className="flex items-center gap-2 text-sm font-medium text-[#242821]">
                                <ShieldCheckIcon className="size-4 text-[#2d6b59]" />
                                Access controls
                            </div>
                            <p className="mt-2 text-xs leading-5 text-[#7b766d]">
                                Team roles, audit trails, and connected calendar permissions stay
                                scoped to each organization.
                            </p>
                        </div>
                    </div>
                </section>

                <footer className="flex flex-col gap-3 border-t border-[#ded7cb] py-5 text-sm text-[#7b766d] sm:flex-row sm:items-center sm:justify-between">
                    <span>© 2026 Surrogacy Force</span>
                    <div className="flex gap-5">
                        <Link href="/privacy" className="transition hover:text-[#1f2521]">
                            Privacy Policy
                        </Link>
                        <Link href="/terms" className="transition hover:text-[#1f2521]">
                            Terms of Service
                        </Link>
                    </div>
                </footer>
            </div>
        </main>
    )
}
