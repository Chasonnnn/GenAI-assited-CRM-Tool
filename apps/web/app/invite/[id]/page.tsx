"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import {
    ArrowRight,
    CheckCircle2,
    Clock,
    Loader2,
    ShieldCheck,
    UserPlus,
    XCircle,
} from "lucide-react"

import { PublicAccessShell } from "@/components/public-access-shell"
import { Button } from "@/components/ui/button"
import api from "@/lib/api"

interface InviteDetails {
    id: string
    organization_id: string
    organization_name: string
    role: string
    inviter_name: string | null
    expires_at: string | null
    status: "pending" | "accepted" | "expired" | "revoked"
}

interface MeResponse {
    org_id: string
    role: string
    display_name: string
}

const ROLE_LABELS: Record<string, string> = {
    intake_specialist: "Intake Specialist",
    case_manager: "Case Manager",
    admin: "Administrator",
    developer: "Developer",
}

function formatRole(role: string | null | undefined) {
    if (!role) {
        return "Pending assignment"
    }

    return ROLE_LABELS[role] ?? role.replaceAll("_", " ")
}

export default function InviteAcceptPage() {
    const params = useParams()
    const rawId = params.id
    const inviteId =
        typeof rawId === "string" ? rawId : Array.isArray(rawId) ? rawId[0] : ""

    const [invite, setInvite] = useState<InviteDetails | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [currentOrgId, setCurrentOrgId] = useState<string | null>(null)

    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    // Fetch invite details
    useEffect(() => {
        async function fetchInvite() {
            try {
                const data = await api.get<InviteDetails>(`/settings/invites/accept/${inviteId}`)
                setInvite(data)
            } catch (err) {
                setError(err instanceof Error ? err.message : "Invite not found")
            } finally {
                setIsLoading(false)
            }
        }

        if (inviteId) {
            fetchInvite()
        }
    }, [inviteId])

    useEffect(() => {
        let active = true
        async function fetchMe() {
            try {
                const me = await api.get<MeResponse>("/auth/me")
                if (active) {
                    setCurrentOrgId(me.org_id)
                }
            } catch {
                // Ignore unauthenticated users
            }
        }
        fetchMe()
        return () => {
            active = false
        }
    }, [])

    const handleSignIn = () => {
        try {
            window.location.assign(`${apiBase}/auth/google/login?return_to=app`)
        } catch {
            // Ignore navigation errors in non-browser runtimes.
        }
    }

    // Format expiry
    const expiryText = invite?.expires_at
        ? `Expires ${new Date(invite.expires_at).toLocaleDateString()}`
        : null

    const alreadyMember = Boolean(invite && currentOrgId && invite.organization_id === currentOrgId)
    const title =
        isLoading
            ? "Loading invite"
            : invite?.status === "accepted"
                ? "Access already activated"
                : invite?.status === "expired"
                    ? "Invite expired"
                    : invite?.status === "revoked"
                        ? "Invite revoked"
                        : error && !invite
                            ? "Invite unavailable"
                            : "You're Invited"

    const description = invite?.inviter_name
        ? `${invite.inviter_name} invited you to join ${invite.organization_name}.`
        : "Review the organization, confirm the assigned role, and continue with Google to enter the workspace."

    const facts =
        invite
            ? [
                { label: "Organization", value: invite.organization_name },
                { label: "Role", value: formatRole(invite.role) },
                { label: "Status", value: invite.status },
            ]
            : []

    return (
        <PublicAccessShell
            title={title}
            description={description}
            facts={facts}
            notes={[
                {
                    label: "Authentication",
                    value: "Continue with your organization Google account. Existing app permissions remain in place.",
                },
                {
                    label: "Membership",
                    value: alreadyMember
                        ? "You already belong to this organization. Signing in will keep your current access."
                        : "Accepted invitations activate access after sign-in.",
                },
                {
                    label: "Invite window",
                    value: expiryText ?? "This invitation stays available until an administrator changes its status.",
                },
            ]}
            panel={
                <div className="space-y-6">
                    <div className="space-y-3">
                        <div className="inline-flex size-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/8">
                            {isLoading ? (
                                <Loader2 className="size-7 animate-spin text-primary" />
                            ) : invite?.status === "accepted" ? (
                                <CheckCircle2 className="size-7 text-[var(--status-success)]" />
                            ) : invite?.status === "expired" || invite?.status === "revoked" || (error && !invite) ? (
                                <XCircle className="size-7 text-[var(--status-danger)]" />
                            ) : (
                                <UserPlus className="size-7 text-primary" strokeWidth={1.6} />
                            )}
                        </div>

                        <div className="space-y-2">
                            <h2 className="font-[family-name:var(--font-display)] text-4xl leading-none text-foreground">
                                {invite?.status === "accepted"
                                    ? "Continue into the workspace."
                                    : invite?.status === "expired"
                                        ? "This invitation has closed."
                                        : invite?.status === "revoked"
                                            ? "This access request was withdrawn."
                                            : error && !invite
                                                ? "We couldn&apos;t verify this invite."
                                                : "Review the assignment, then continue."}
                            </h2>
                            <p className="text-sm leading-6 text-muted-foreground">
                                {invite?.status === "accepted"
                                    ? "Your membership is already active. Sign in with Google to continue."
                                    : invite?.status === "expired"
                                        ? "Ask the inviter to send a new invitation if you still need access."
                                        : invite?.status === "revoked"
                                            ? "An administrator revoked this invitation before sign-in."
                                            : error && !invite
                                                ? error
                                                : "Continue with Google to confirm the invite and open the correct Surrogacy Force workspace."}
                            </p>
                        </div>
                    </div>

                    {invite?.status === "pending" ? (
                        <>
                            <div className="rounded-3xl border border-border/80 bg-background px-5 py-5">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="space-y-1">
                                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                                            Invitation summary
                                        </p>
                                        <p className="text-base font-medium text-foreground">
                                            {invite?.organization_name}
                                        </p>
                                    </div>
                                    {expiryText ? (
                                        <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground">
                                            <Clock className="size-3.5" />
                                            {expiryText}
                                        </span>
                                    ) : null}
                                </div>

                                <div className="mt-4 grid gap-3 border-t border-border/70 pt-4 sm:grid-cols-2">
                                    <div>
                                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                                            Assigned org
                                        </p>
                                        <p className="mt-1 text-sm font-medium text-foreground">
                                            {invite?.organization_name}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                                            Access role
                                        </p>
                                        <p className="mt-1 text-sm font-medium text-foreground">
                                            {formatRole(invite?.role)}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {error ? (
                                <div className="rounded-2xl border border-[var(--status-danger)]/30 bg-[var(--status-danger)]/8 px-4 py-3 text-sm text-foreground">
                                    {error}
                                </div>
                            ) : null}

                            {alreadyMember ? (
                                <div className="rounded-2xl border border-primary/20 bg-primary/8 px-4 py-3 text-sm leading-6 text-foreground">
                                    You already have access to this organization. This invite won&apos;t change your role. Sign in and ask an administrator to adjust permissions if needed.
                                </div>
                            ) : null}

                            <Button
                                onClick={handleSignIn}
                                className="h-13 w-full justify-between rounded-full px-5 text-base font-semibold"
                            >
                                <span className="inline-flex items-center gap-2">
                                    <ShieldCheck className="size-5" />
                                    Continue with Google
                                </span>
                                <ArrowRight className="size-5" />
                            </Button>
                        </>
                    ) : invite?.status === "accepted" ? (
                        <>
                            {alreadyMember ? (
                                <div className="rounded-2xl border border-primary/20 bg-primary/8 px-4 py-3 text-sm leading-6 text-foreground">
                                    You already have access to this organization. Signing in will keep your current access and won&apos;t overwrite your role.
                                </div>
                            ) : null}

                            <Button
                                onClick={handleSignIn}
                                className="h-13 w-full justify-between rounded-full px-5 text-base font-semibold"
                            >
                                <span className="inline-flex items-center gap-2">
                                    <ShieldCheck className="size-5" />
                                    Continue to Sign In
                                </span>
                                <ArrowRight className="size-5" />
                            </Button>
                        </>
                    ) : (
                        <div className="rounded-2xl border border-border/70 bg-background px-5 py-5 text-sm leading-6 text-muted-foreground">
                            {invite?.status === "expired"
                                ? "Ask the inviter to send a new invitation if you still need access."
                                : invite?.status === "revoked"
                                    ? "If this was unexpected, contact your administrator before attempting to sign in."
                                    : "If you believe this invite should still work, contact your administrator to verify the link and your account."}
                        </div>
                    )}
                </div>
            }
            footer={
                <div className="flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                    <span>Need help with your invitation? Contact the administrator who sent it.</span>
                    <span>© 2025 Surrogacy Force</span>
                </div>
            }
        />
    )
}
