"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ShieldCheck, UserPlus, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react"
import api from "@/lib/api"

interface InviteDetails {
    id: string
    organization_name: string
    role: string
    inviter_name: string | null
    expires_at: string | null
    status: "pending" | "accepted" | "expired" | "revoked"
}

export default function InviteAcceptPage() {
    const params = useParams()
    const rawId = params.id
    const inviteId =
        typeof rawId === "string" ? rawId : Array.isArray(rawId) ? rawId[0] : ""

    const [invite, setInvite] = useState<InviteDetails | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

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

    return (
        <div
            className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
            style={{
                background: "linear-gradient(135deg, #f8f9fa 0%, #f1f3f5 50%, #f8f9fa 100%)",
            }}
        >
            {/* Background blobs */}
            <div
                className="absolute -left-32 top-1/2 w-[600px] h-[600px] rounded-full blur-3xl"
                style={{
                    background: "radial-gradient(circle, rgba(99, 102, 241, 0.6) 0%, rgba(139, 92, 246, 0.5) 40%, transparent 70%)",
                }}
            />
            <div
                className="absolute -right-32 top-0 w-[500px] h-[500px] rounded-full blur-3xl"
                style={{
                    background: "radial-gradient(circle, rgba(34, 197, 94, 0.4) 0%, rgba(74, 222, 128, 0.3) 40%, transparent 70%)",
                }}
            />

            <Card
                className="w-full max-w-md relative z-10 border border-white/40 shadow-2xl"
                style={{
                    background: "linear-gradient(180deg, rgba(255, 255, 255, 0.7) 0%, rgba(240, 253, 244, 0.6) 100%)",
                    backdropFilter: "blur(24px) saturate(180%)",
                    WebkitBackdropFilter: "blur(24px) saturate(180%)",
                    boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                }}
            >
                <CardHeader className="text-center space-y-4 pb-2">
                    <div className="flex justify-center mb-2">
                        <div className="w-14 h-14 rounded-xl flex items-center justify-center bg-green-100 border border-green-200">
                            <UserPlus className="w-8 h-8 text-green-700" strokeWidth={1.5} />
                        </div>
                    </div>
                    <div className="space-y-1">
                        <div className="text-xs font-semibold text-gray-500 tracking-widest">SURROGACY FORCE</div>
                        <CardTitle className="text-3xl font-bold text-gray-900">
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
                            <Loader2 className="size-8 animate-spin text-gray-400" />
                        </div>
                    ) : error && !invite ? (
                        <div className="text-center py-6">
                            <XCircle className="size-12 mx-auto mb-4 text-red-400" />
                            <p className="text-gray-600">{error}</p>
                        </div>
                    ) : invite?.status !== "pending" ? (
                        <div className="text-center py-6">
                            {invite?.status === "accepted" ? (
                                <CheckCircle2 className="size-12 mx-auto mb-4 text-green-500" />
                            ) : (
                                <XCircle className="size-12 mx-auto mb-4 text-gray-400" />
                            )}
                            <p className="text-gray-600">
                                This invite is {invite?.status}.
                            </p>
                            {invite?.status === "expired" && (
                                <p className="text-sm text-gray-500 mt-2">
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
                            <CardDescription className="text-center text-gray-600">
                                {invite?.inviter_name ? (
                                    <>
                                        <strong>{invite.inviter_name}</strong> invited you to join
                                    </>
                                ) : (
                                    "You've been invited to join"
                                )}
                            </CardDescription>

                            <div className="bg-white/60 rounded-xl p-4 border border-gray-200/50 space-y-3">
                                <div className="flex justify-between items-center">
                                    <span className="text-sm text-gray-500">Organization</span>
                                    <span className="font-semibold text-gray-900">{invite?.organization_name}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-sm text-gray-500">Role</span>
                                    <span className="font-semibold text-gray-900 capitalize">{invite?.role}</span>
                                </div>
                                {expiryText && (
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm text-gray-500">Expires</span>
                                        <span className="text-sm text-gray-600 flex items-center gap-1">
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

                            <div className="relative py-2">
                                <div className="absolute inset-0 flex items-center">
                                    <span className="w-full border-t border-gray-300/50" />
                                </div>
                                <div className="relative flex justify-center text-xs uppercase">
                                    <span className="px-3 bg-transparent text-gray-500 font-medium tracking-wider">
                                        Continue to sign in
                                    </span>
                                </div>
                            </div>

                            <Button
                                onClick={handleSignIn}
                                variant="outline"
                                className="w-full border-gray-300 text-gray-700 hover:bg-gray-50 font-semibold py-5 rounded-lg"
                            >
                                <ShieldCheck className="size-5 mr-2" />
                                Continue with Google
                            </Button>
                        </>
                    )}

                    <div className="pt-4 border-t border-gray-100">
                        <div className="text-center">
                            <p className="text-xs text-gray-400">© 2025 Surrogacy Force. All rights reserved.</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
