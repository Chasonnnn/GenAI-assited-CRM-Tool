"use client"

import { useParams } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ShieldCheck, UserPlus, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react"
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

export default function InviteAcceptPageClient() {
    const params = useParams()
    const rawId = params.id
    const inviteId =
        typeof rawId === "string" ? rawId : Array.isArray(rawId) ? rawId[0] : ""

    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    const inviteQuery = useQuery({
        queryKey: ["invite-accept", inviteId],
        queryFn: () => api.get<InviteDetails>(`/settings/invites/accept/${inviteId}`),
        enabled: Boolean(inviteId),
        retry: false,
    })
    const currentUserQuery = useQuery({
        queryKey: ["invite-accept", "current-user"],
        queryFn: () => api.get<MeResponse>("/auth/me"),
        retry: false,
    })
    const invite = inviteQuery.data ?? null
    const isLoading = inviteQuery.isLoading
    const error = inviteQuery.error instanceof Error
        ? inviteQuery.error.message
        : inviteQuery.error
          ? "Invite not found"
          : null
    const currentOrgId = currentUserQuery.data?.org_id ?? null

    const handleSignIn = () => {
        try {
            const params = new URLSearchParams({ return_to: "app" })
            if (inviteId) {
                params.set("invite_id", inviteId)
            }
            window.location.assign(`${apiBase}/auth/google/login?${params.toString()}`)
        } catch {
            // Ignore navigation errors in non-browser runtimes.
        }
    }

    // Format expiry
    const expiryText = invite?.expires_at
        ? `Expires ${new Date(invite.expires_at).toLocaleDateString()}`
        : null

    const alreadyMember = Boolean(invite && currentOrgId && invite.organization_id === currentOrgId)

    return (
        <div
            className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
            style={{
                background: "linear-gradient(135deg, #f8f9fa 0%, #f1f3f5 50%, #f8f9fa 100%)",
            }}
        >
            {/* Background blobs */}
            <div
                className="absolute -left-32 top-1/2 size-[600px] rounded-full blur-3xl"
                style={{
                    background: "radial-gradient(circle, rgba(99, 102, 241, 0.6) 0%, rgba(139, 92, 246, 0.5) 40%, transparent 70%)",
                }}
            />
            <div
                className="absolute -right-32 top-0 size-[500px] rounded-full blur-3xl"
                style={{
                    background: "radial-gradient(circle, rgba(34, 197, 94, 0.4) 0%, rgba(74, 222, 128, 0.3) 40%, transparent 70%)",
                }}
            />

            <Card
                className="w-full max-w-md relative z-10 border border-white/40 shadow-2xl"
                style={{
                    background: "linear-gradient(180deg, rgba(255, 255, 255, 0.7) 0%, rgba(240, 253, 244, 0.6) 100%)",
                    backdropFilter: "blur(8px) saturate(160%)",
                    WebkitBackdropFilter: "blur(8px) saturate(160%)",
                    boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                }}
            >
                <CardHeader className="text-center space-y-4 pb-2">
                    <div className="flex justify-center mb-2">
                        <div className="size-14 rounded-xl flex items-center justify-center bg-green-100 border border-green-200">
                            <UserPlus className="size-8 text-green-700" strokeWidth={1.5} />
                        </div>
                    </div>
                    <div className="space-y-1">
                        <div className="text-xs font-semibold text-zinc-500 tracking-widest">SURROGACY FORCE</div>
                        <CardTitle className="text-3xl font-bold text-zinc-900">
                            {isLoading
                                ? "Loading..."
                                : invite?.status === "accepted"
                                    ? "Welcome!"
                                    : "You're Invited"}
                        </CardTitle>
                    </div>
                </CardHeader>

                <CardContent className="space-y-5">
                    {isLoading ? (
                        <div className="flex justify-center py-8">
                            <Loader2 className="size-8 animate-spin text-zinc-400" />
                        </div>
                    ) : error && !invite ? (
                        <div className="text-center py-6">
                            <XCircle className="size-12 mx-auto mb-4 text-red-400" />
                            <p className="text-zinc-600">{error}</p>
                        </div>
                    ) : invite?.status !== "pending" ? (
                        <div className="text-center py-6">
                            {invite?.status === "accepted" ? (
                                <CheckCircle2 className="size-12 mx-auto mb-4 text-green-500" />
                            ) : (
                                <XCircle className="size-12 mx-auto mb-4 text-zinc-400" />
                            )}
                            <p className="text-zinc-600">
                                This invite is {invite?.status}.
                            </p>
                            {alreadyMember && (
                                <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-left text-sm text-blue-700">
                                    You already have access to this organization. This invite won&apos;t change your role.
                                    Sign in and ask an admin to update your role if needed.
                                </div>
                            )}
                            {invite?.status === "expired" && (
                                <p className="text-sm text-zinc-500 mt-2">
                                    Ask the inviter to send a new invitation.
                                </p>
                            )}
                            {invite?.status === "accepted" && (
                                <Button
                                    onClick={handleSignIn}
                                    className="mt-6 w-full font-semibold py-5 rounded-lg bg-green-700 text-white hover:bg-green-800"
                                >
                                    <ShieldCheck className="size-5 mr-2" />
                                    Continue to Sign In
                                </Button>
                            )}
                        </div>
                    ) : (
                        <>
                            <CardDescription className="text-center text-zinc-600">
                                {invite?.inviter_name ? (
                                    <>
                                        <strong>{invite.inviter_name}</strong> invited you to join
                                    </>
                                ) : (
                                    "You've been invited to join"
                                )}
                            </CardDescription>

                            <div className="bg-white/60 rounded-xl p-4 border border-zinc-200/50 space-y-3">
                                <div className="flex justify-between items-center">
                                    <span className="text-sm text-zinc-500">Organization</span>
                                    <span className="font-semibold text-zinc-900">{invite?.organization_name}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-sm text-zinc-500">Role</span>
                                    <span className="font-semibold text-zinc-900 capitalize">{invite?.role}</span>
                                </div>
                                {expiryText && (
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm text-zinc-500">Expires</span>
                                        <span className="text-sm text-zinc-600 flex items-center gap-1">
                                            <Clock className="size-3" />
                                            {expiryText}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {error && (
                                <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg border border-red-200">
                                    {error}
                                </div>
                            )}
                            {alreadyMember && (
                                <div className="bg-blue-50 text-blue-700 text-sm p-3 rounded-lg border border-blue-200">
                                    You already have access to this organization. This invite won&apos;t change your role.
                                    Sign in and ask an admin to update your role if needed.
                                </div>
                            )}

                            <div className="relative py-2">
                                <div className="absolute inset-0 flex items-center">
                                    <span className="w-full border-t border-zinc-300/50" />
                                </div>
                                <div className="relative flex justify-center text-xs uppercase">
                                    <span className="px-3 bg-transparent text-zinc-500 font-medium tracking-wider">
                                        Continue to sign in
                                    </span>
                                </div>
                            </div>

                            <Button
                                onClick={handleSignIn}
                                variant="outline"
                                className="w-full border-zinc-300 text-zinc-700 hover:bg-zinc-50 font-semibold py-5 rounded-lg"
                            >
                                <ShieldCheck className="size-5 mr-2" />
                                Continue with Google
                            </Button>
                        </>
                    )}

                    <div className="pt-4 border-t border-zinc-100">
                        <div className="text-center">
                            <p className="text-xs text-zinc-400">© 2025 Surrogacy Force. All rights reserved.</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
