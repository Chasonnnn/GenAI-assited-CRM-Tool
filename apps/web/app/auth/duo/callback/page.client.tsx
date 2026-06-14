"use client"

import { useEffect, useReducer, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { CheckIcon, CopyIcon, KeyIcon, Loader2Icon } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { verifyDuoCallback } from "@/lib/api/mfa"

function hasAuthReturnToOpsCookie(): boolean {
    if (typeof document === "undefined") return false
    return document.cookie.split(";").some((c) => c.trim().startsWith("auth_return_to=ops"))
}

function getStoredAuthReturnTo(): string | null {
    try {
        return sessionStorage.getItem("auth_return_to")
    } catch {
        return null
    }
}

function setStoredAuthReturnTo(value: string) {
    try {
        sessionStorage.setItem("auth_return_to", value)
    } catch {
        // Ignore storage errors in restricted browser contexts.
    }
}

function clearStoredAuthReturnTo() {
    try {
        sessionStorage.removeItem("auth_return_to")
    } catch {
        // Ignore storage errors in restricted browser contexts.
    }
}

const APP_POST_MFA_PATH = "/dashboard"

const duoVerifyAttempts = new Set<string>()

type DuoCallbackState = {
    status: "loading" | "error" | "success"
    errorMessage: string | null
    recoveryCodes: string[] | null
}

type DuoCallbackAction =
    | { type: "error"; message: string }
    | { type: "success"; recoveryCodes?: string[] | null }
    | { type: "clearRecoveryCodes" }

const initialDuoCallbackState: DuoCallbackState = {
    status: "loading",
    errorMessage: null,
    recoveryCodes: null,
}

function duoCallbackReducer(state: DuoCallbackState, action: DuoCallbackAction): DuoCallbackState {
    switch (action.type) {
        case "error":
            return {
                status: "error",
                errorMessage: action.message,
                recoveryCodes: null,
            }
        case "success":
            return {
                status: "success",
                errorMessage: null,
                recoveryCodes: action.recoveryCodes ?? null,
            }
        case "clearRecoveryCodes":
            return {
                ...state,
                recoveryCodes: null,
            }
        default:
            return state
    }
}

function RecoveryCodesDisplay({ codes, onClose }: { codes: string[]; onClose: () => void }) {
    const [copied, setCopied] = useState(false)

    const handleCopy = () => {
        void navigator.clipboard.writeText(codes.join("\n"))
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <Dialog open={true} onOpenChange={onClose}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <KeyIcon className="size-5" />
                        Recovery Codes
                    </DialogTitle>
                    <DialogDescription>
                        Save these codes in a secure location. Each code can only be used once.
                    </DialogDescription>
                </DialogHeader>

                <Alert variant="destructive" className="my-4">
                    <AlertTitle>Important</AlertTitle>
                    <AlertDescription>
                        These codes will not be shown again. Save them now.
                    </AlertDescription>
                </Alert>

                <div className="grid grid-cols-2 gap-2 p-4 bg-muted rounded-lg font-mono text-sm">
                    {codes.map((code) => (
                        <div key={code} className="p-2 bg-background rounded text-center">
                            {code}
                        </div>
                    ))}
                </div>

                <DialogFooter className="gap-2">
                    <Button variant="outline" onClick={handleCopy}>
                        {copied ? (
                            <>
                                <CheckIcon className="size-4 mr-2" />
                                Copied
                            </>
                        ) : (
                            <>
                                <CopyIcon className="size-4 mr-2" />
                                Copy All
                            </>
                        )}
                    </Button>
                    <Button onClick={onClose}>I have saved these codes</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default function DuoCallbackPage() {
    const { replace } = useRouter()
    const { user, isLoading: authLoading, refetch: refreshAuth } = useAuth()

    const [{ status, errorMessage, recoveryCodes }, dispatch] = useReducer(
        duoCallbackReducer,
        initialDuoCallbackState,
    )

    useEffect(() => {
        if (authLoading) return
        if (!user) {
            const urlReturnTo = new URLSearchParams(window.location.search).get("return_to")
            const returnTo =
                getStoredAuthReturnTo() === "ops" ||
                urlReturnTo === "ops" ||
                hasAuthReturnToOpsCookie() ||
                window.location.hostname.startsWith("ops.")
                    ? "ops"
                    : "app"

            if (returnTo === "ops") {
                replace("/ops/login")
                return
            }

            replace("/login")
        }
    }, [authLoading, user, replace])

    useEffect(() => {
        if (authLoading || !user) return

        const urlParams = new URLSearchParams(window.location.search)
        const returnTo =
            getStoredAuthReturnTo() === "ops" ||
            urlParams.get("return_to") === "ops" ||
            hasAuthReturnToOpsCookie() ||
            window.location.hostname.startsWith("ops.")
                ? "ops"
                : "app"

        if (returnTo === "ops") {
            setStoredAuthReturnTo("ops")
        }

        // Duo Web SDK can return the authorization parameter as `duo_code` (default) or `code`.
        const code = urlParams.get("duo_code") ?? urlParams.get("code")
        const state = urlParams.get("state")
        if (!code || !state) {
            dispatch({
                type: "error",
                message: "Missing Duo response parameters. Please try again.",
            })
            return
        }

        const attemptKey = `${code}:${state}:${returnTo}`
        if (duoVerifyAttempts.has(attemptKey)) {
            return
        }
        duoVerifyAttempts.add(attemptKey)

        const verify = async () => {
            try {
                const result = await verifyDuoCallback(code, state, returnTo)
                const resultRecoveryCodes =
                    result.recovery_codes && result.recovery_codes.length > 0
                        ? result.recovery_codes
                        : null
                await refreshAuth()
                dispatch({ type: "success", recoveryCodes: resultRecoveryCodes })
                if (!resultRecoveryCodes) {
                    if (returnTo === "ops") {
                        clearStoredAuthReturnTo()
                        replace("/ops")
                        return
                    }
                    replace(APP_POST_MFA_PATH)
                }
            } catch (error) {
                console.error("Duo verification failed:", error)
                dispatch({
                    type: "error",
                    message: "Duo verification failed. Please try again.",
                })
            }
        }

        void verify()
    }, [authLoading, user, refreshAuth, replace])

    return (
        <div className="min-h-screen flex items-center justify-center bg-muted/30 p-6">
            <Card className="w-full max-w-lg shadow-lg">
                <CardHeader className="text-center">
                    <CardTitle>Duo verification</CardTitle>
                    <CardDescription>Completing authentication</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 text-center">
                    {status === "loading" && (
                        <div className="flex flex-col items-center gap-3">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">Verifying Duo response&hellip;</p>
                        </div>
                    )}

                    {status === "error" && (
                        <Alert variant="destructive" className="text-left">
                            <AlertTitle>Verification failed</AlertTitle>
                            <AlertDescription>{errorMessage}</AlertDescription>
                            <div className="mt-4">
                                <Button onClick={() => replace("/mfa")} className="w-full">
                                    Return to MFA
                                </Button>
                            </div>
                        </Alert>
                    )}

                    {status === "success" && (
                        <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">Duo verification complete.</p>
                            <Button onClick={() => replace(APP_POST_MFA_PATH)}>Continue to dashboard</Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {recoveryCodes && (
                <RecoveryCodesDisplay
                    codes={recoveryCodes}
                    onClose={() => {
                        dispatch({ type: "clearRecoveryCodes" })
                        const urlReturnTo = new URLSearchParams(window.location.search).get("return_to")
                        const returnTo =
                            getStoredAuthReturnTo() === "ops" ||
                            urlReturnTo === "ops" ||
                            hasAuthReturnToOpsCookie() ||
                            window.location.hostname.startsWith("ops.")
                                ? "ops"
                                : "app"
                        if (returnTo === "ops") {
                            clearStoredAuthReturnTo()
                            replace("/ops")
                            return
                        }
                        replace(APP_POST_MFA_PATH)
                    }}
                />
            )}
        </div>
    )
}
