"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
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

function RecoveryCodesDisplay({ codes, onClose }: { codes: string[]; onClose: () => void }) {
    const [copied, setCopied] = useState(false)

    const handleCopy = () => {
        navigator.clipboard.writeText(codes.join("\n"))
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
                    {codes.map((code, i) => (
                        <div key={i} className="p-2 bg-background rounded text-center">
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

function DuoCallbackContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const { user, isLoading: authLoading, refetch } = useAuth()

    const [status, setStatus] = useState<"loading" | "error" | "success">("loading")
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)

    useEffect(() => {
        if (authLoading) return
        if (!user) {
            const returnTo = sessionStorage.getItem("auth_return_to")
            if (returnTo === "ops") {
                router.replace("/ops/login")
                return
            }
            router.replace("/login")
        }
    }, [authLoading, user, router])

    useEffect(() => {
        if (authLoading || !user) return

        const code = searchParams.get("code")
        const state = searchParams.get("state")
        const expectedState = sessionStorage.getItem("duo_state")

        if (!code || !state) {
            setStatus("error")
            setErrorMessage("Missing Duo response parameters. Please try again.")
            return
        }

        if (!expectedState || expectedState !== state) {
            setStatus("error")
            setErrorMessage("Duo session mismatch. Please restart verification.")
            return
        }

        sessionStorage.removeItem("duo_state")

        const verify = async () => {
            try {
                const result = await verifyDuoCallback(code, state, expectedState)
                if (result.recovery_codes && result.recovery_codes.length > 0) {
                    setRecoveryCodes(result.recovery_codes)
                }
                await refetch()
                setStatus("success")
                if (!result.recovery_codes || result.recovery_codes.length === 0) {
                    const returnTo = sessionStorage.getItem("auth_return_to")
                    if (returnTo === "ops") {
                        sessionStorage.removeItem("auth_return_to")
                        router.replace("/ops")
                        return
                    }
                    router.replace("/")
                }
            } catch (error) {
                console.error("Duo verification failed:", error)
                setStatus("error")
                setErrorMessage("Duo verification failed. Please try again.")
            }
        }

        verify()
    }, [authLoading, user, searchParams, refetch, router])

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
                            <p className="text-sm text-muted-foreground">Verifying Duo response...</p>
                        </div>
                    )}

                    {status === "error" && (
                        <Alert variant="destructive" className="text-left">
                            <AlertTitle>Verification failed</AlertTitle>
                            <AlertDescription>{errorMessage}</AlertDescription>
                            <div className="mt-4">
                                <Button onClick={() => router.replace("/mfa")} className="w-full">
                                    Return to MFA
                                </Button>
                            </div>
                        </Alert>
                    )}

                    {status === "success" && (
                        <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">Duo verification complete.</p>
                            <Button onClick={() => router.replace("/")}>Continue</Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {recoveryCodes && (
                <RecoveryCodesDisplay
                    codes={recoveryCodes}
                    onClose={() => {
                        setRecoveryCodes(null)
                        const returnTo = sessionStorage.getItem("auth_return_to")
                        if (returnTo === "ops") {
                            sessionStorage.removeItem("auth_return_to")
                            router.replace("/ops")
                            return
                        }
                        router.replace("/")
                    }}
                />
            )}
        </div>
    )
}

export default function DuoCallbackPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen flex items-center justify-center bg-muted/30">
                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                </div>
            }
        >
            <DuoCallbackContent />
        </Suspense>
    )
}
