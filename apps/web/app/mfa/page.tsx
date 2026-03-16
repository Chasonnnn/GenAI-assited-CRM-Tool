"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Loader2Icon, ShieldCheckIcon } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
    useCompleteMFAChallenge,
    useDuoStatus,
    useInitiateDuoAuth,
    useMFAStatus,
} from "@/lib/hooks/use-mfa"

function hasAuthReturnToOpsCookie(): boolean {
    if (typeof document === "undefined") return false
    return document.cookie.split(";").some((c) => c.trim().startsWith("auth_return_to=ops"))
}

const APP_POST_MFA_PATH = "/dashboard"

export default function MFAPage() {
    const router = useRouter()
    const { user, isLoading: authLoading, refetch } = useAuth()
    const { data: mfaStatus, isLoading: mfaLoading } = useMFAStatus()
    const { data: duoStatus } = useDuoStatus()

    const completeMFA = useCompleteMFAChallenge()
    const initiateDuo = useInitiateDuoAuth()

    const [challengeCode, setChallengeCode] = useState("")
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [showCodeEntry, setShowCodeEntry] = useState(false)

    useEffect(() => {
        // Ensure ops flows keep "return_to=ops" even if the user landed here without coming from /ops/login.
        if (typeof window === "undefined") return
        const queryReturnTo = new URLSearchParams(window.location.search).get("return_to")
        const isOps =
            queryReturnTo === "ops" ||
            hasAuthReturnToOpsCookie() ||
            sessionStorage.getItem("auth_return_to") === "ops" ||
            window.location.hostname.startsWith("ops.")
        if (isOps) {
            sessionStorage.setItem("auth_return_to", "ops")
        }
    }, [])

    useEffect(() => {
        if (authLoading) return
        if (!user) {
            router.replace("/login")
            return
        }
        if (!user.mfa_required || user.mfa_verified) {
            const returnTo = sessionStorage.getItem("auth_return_to")
            if (returnTo === "ops") {
                sessionStorage.removeItem("auth_return_to")
                router.replace("/ops")
                return
            }
            router.replace(APP_POST_MFA_PATH)
        }
    }, [authLoading, user, router])

    const handleChallenge = async () => {
        if (!challengeCode) return
        setErrorMessage(null)
        try {
            const returnTo = sessionStorage.getItem("auth_return_to")
            await completeMFA.mutateAsync(challengeCode)
            await refetch()
            if (returnTo === "ops") {
                sessionStorage.removeItem("auth_return_to")
                router.replace("/ops")
                return
            }
            router.replace(APP_POST_MFA_PATH)
        } catch (error) {
            console.error("MFA challenge failed:", error)
            setErrorMessage("Invalid code. Please try again.")
        }
    }

    const handleDuo = async () => {
        setErrorMessage(null)
        try {
            const queryReturnTo = new URLSearchParams(window.location.search).get("return_to")
            const returnTo =
                queryReturnTo === "ops" ||
                hasAuthReturnToOpsCookie() ||
                sessionStorage.getItem("auth_return_to") === "ops" ||
                (typeof window !== "undefined" && window.location.hostname.startsWith("ops."))
                    ? "ops"
                    : undefined
            if (returnTo === "ops") {
                sessionStorage.setItem("auth_return_to", "ops")
            }
            const result = await initiateDuo.mutateAsync(returnTo)
            window.location.assign(result.auth_url)
        } catch (error) {
            console.error("Failed to initiate Duo:", error)
            setErrorMessage("Unable to start Duo verification. Please try again.")
        }
    }

    if (authLoading || mfaLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    const duoAvailable = duoStatus?.available
    const duoEnrolled = duoStatus?.enrolled
    const mfaEnabled = mfaStatus?.mfa_enabled
    const canUseDuo = Boolean(duoAvailable)

    return (
        <div className="min-h-screen flex items-center justify-center bg-muted/30 p-6">
            <Card className="w-full max-w-lg shadow-lg">
                <CardHeader className="space-y-2 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                        <ShieldCheckIcon className="size-6 text-muted-foreground" />
                    </div>
                    <CardTitle>Multi-factor authentication required</CardTitle>
                    <CardDescription>
                        {user ? `Continue as ${user.email}` : "Verify your identity to continue"}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {errorMessage && (
                        <Alert variant="destructive">
                            <AlertTitle>Action needed</AlertTitle>
                            <AlertDescription>{errorMessage}</AlertDescription>
                        </Alert>
                    )}

                    {!mfaEnabled && (
                        <div className="space-y-4">
                            {duoAvailable ? (
                                <div className="rounded-lg border border-dashed p-4">
                                    <h3 className="text-sm font-semibold mb-1">Duo Security</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Set up Duo for this account to continue.
                                    </p>
                                    <div className="mt-3">
                                        <Button
                                            onClick={handleDuo}
                                            disabled={initiateDuo.isPending}
                                            className="w-full"
                                        >
                                            {initiateDuo.isPending ? "Starting Duo..." : "Set up Duo"}
                                        </Button>
                                    </div>
                                </div>
                            ) : (
                                <Alert variant="destructive">
                                    <AlertTitle>Duo unavailable</AlertTitle>
                                    <AlertDescription>
                                        Duo setup is temporarily unavailable. Please try again later or
                                        contact support.
                                    </AlertDescription>
                                </Alert>
                            )}
                        </div>
                    )}

                    {mfaEnabled && (
                        <div className="space-y-4">
                            {canUseDuo && (
                                <Button
                                    onClick={handleDuo}
                                    disabled={initiateDuo.isPending}
                                    className="w-full"
                                >
                                    {initiateDuo.isPending
                                        ? "Starting Duo..."
                                        : duoEnrolled
                                          ? "Continue with Duo"
                                          : "Set up Duo"}
                                </Button>
                            )}

                            {(showCodeEntry || !canUseDuo) && (
                                <>
                                    <div className="space-y-2">
                                        <Label htmlFor="challenge-code">Recovery code</Label>
                                        <Input
                                            id="challenge-code"
                                            placeholder="Enter recovery code"
                                            value={challengeCode}
                                            onChange={(event) => setChallengeCode(event.target.value)}
                                        />
                                    </div>
                                    <Button
                                        variant="outline"
                                        onClick={handleChallenge}
                                        disabled={completeMFA.isPending}
                                        className="w-full"
                                    >
                                        {completeMFA.isPending ? "Verifying..." : "Verify code"}
                                    </Button>
                                </>
                            )}

                            {canUseDuo && !showCodeEntry && (
                                <Button
                                    variant="ghost"
                                    onClick={() => setShowCodeEntry(true)}
                                    className="w-full"
                                >
                                    Use recovery code instead
                                </Button>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
