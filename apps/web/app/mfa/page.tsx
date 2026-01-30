"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    CheckIcon,
    CopyIcon,
    KeyIcon,
    Loader2Icon,
    ShieldCheckIcon,
    SmartphoneIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import {
    useCompleteMFAChallenge,
    useDuoStatus,
    useInitiateDuoAuth,
    useMFAStatus,
    useSetupTOTP,
    useVerifyTOTPSetup,
} from "@/lib/hooks/use-mfa"

function hasAuthReturnToOpsCookie(): boolean {
    if (typeof document === "undefined") return false
    return document.cookie.split(";").some((c) => c.trim().startsWith("auth_return_to=ops"))
}

function QRCodeDisplay({ data }: { data: string }) {
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(data)}`

    return (
        <div className="flex justify-center p-4 bg-white rounded-lg">
            <img
                src={qrUrl}
                alt="TOTP QR Code"
                width={200}
                height={200}
                className="rounded"
            />
        </div>
    )
}

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

export default function MFAPage() {
    return (
        <Suspense
            fallback={
                <div className="flex min-h-screen items-center justify-center">
                    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                </div>
            }
        >
            <MFAPageContent />
        </Suspense>
    )
}

function MFAPageContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const { user, isLoading: authLoading, refetch } = useAuth()
    const { data: mfaStatus, isLoading: mfaLoading } = useMFAStatus()
    const { data: duoStatus } = useDuoStatus()

    const setupTOTP = useSetupTOTP()
    const verifyTOTP = useVerifyTOTPSetup()
    const completeMFA = useCompleteMFAChallenge()
    const initiateDuo = useInitiateDuoAuth()

    const [setupData, setSetupData] = useState<{ secret: string; provisioning_uri: string } | null>(null)
    const [setupCode, setSetupCode] = useState("")
    const [challengeCode, setChallengeCode] = useState("")
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
    const [showCodeEntry, setShowCodeEntry] = useState(false)

    useEffect(() => {
        // Ensure ops flows keep "return_to=ops" even if the user landed here without coming from /ops/login.
        if (typeof window === "undefined") return
        const queryReturnTo = searchParams.get("return_to")
        const isOps =
            queryReturnTo === "ops" ||
            hasAuthReturnToOpsCookie() ||
            sessionStorage.getItem("auth_return_to") === "ops" ||
            window.location.hostname.startsWith("ops.")
        if (isOps) {
            sessionStorage.setItem("auth_return_to", "ops")
        }
    }, [searchParams])

    useEffect(() => {
        if (authLoading) return
        if (recoveryCodes) return
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
            router.replace("/")
        }
    }, [authLoading, user, router, recoveryCodes])

    const handleStartSetup = async () => {
        setErrorMessage(null)
        try {
            const data = await setupTOTP.mutateAsync()
            setSetupData(data)
        } catch (error) {
            console.error("Failed to start TOTP setup:", error)
            setErrorMessage("Unable to start authenticator setup. Please try again.")
        }
    }

    const handleVerifySetup = async () => {
        if (!setupCode) return
        setErrorMessage(null)
        try {
            const result = await verifyTOTP.mutateAsync(setupCode)
            if (result.success) {
                setRecoveryCodes(result.recovery_codes)
                await completeMFA.mutateAsync(setupCode)
                await refetch()
                setSetupData(null)
                setSetupCode("")
            }
        } catch (error) {
            console.error("Verification failed:", error)
            setErrorMessage("Verification failed. Please check the code and try again.")
        }
    }

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
            router.replace("/")
        } catch (error) {
            console.error("MFA challenge failed:", error)
            setErrorMessage("Invalid code. Please try again.")
        }
    }

    const handleDuo = async () => {
        setErrorMessage(null)
        try {
            const queryReturnTo = searchParams.get("return_to")
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
    const totpEnabled = mfaStatus?.totp_enabled

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
                            {duoAvailable && !duoEnrolled && (
                                <div className="rounded-lg border border-dashed p-4">
                                    <h3 className="text-sm font-semibold mb-1">Duo Security</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Continue with Duo (recommended).
                                    </p>
                                    <div className="mt-3">
                                        <Button
                                            onClick={handleDuo}
                                            disabled={initiateDuo.isPending}
                                            className="w-full"
                                        >
                                            {initiateDuo.isPending ? "Starting Duo..." : "Continue with Duo"}
                                        </Button>
                                    </div>
                                </div>
                            )}

                            <div className="rounded-lg border border-dashed p-4">
                                <h3 className="text-sm font-semibold mb-1 flex items-center gap-2">
                                    <SmartphoneIcon className="size-4" />
                                    Authenticator app
                                </h3>
                                <p className="text-sm text-muted-foreground">
                                    Use Google Authenticator, Authy, or 1Password to scan a QR code.
                                </p>
                                <div className="mt-3">
                                    <Button
                                        onClick={handleStartSetup}
                                        disabled={setupTOTP.isPending}
                                        className="w-full"
                                    >
                                        {setupTOTP.isPending ? "Preparing..." : "Set up authenticator"}
                                    </Button>
                                </div>
                            </div>

                            {setupData && (
                                <div className="space-y-4 rounded-lg border p-4">
                                    <QRCodeDisplay data={setupData.provisioning_uri} />
                                    <div className="space-y-2">
                                        <Label htmlFor="setup-code">Authenticator code</Label>
                                        <Input
                                            id="setup-code"
                                            placeholder="123456"
                                            value={setupCode}
                                            onChange={(event) => setSetupCode(event.target.value)}
                                        />
                                    </div>
                                    <Button
                                        onClick={handleVerifySetup}
                                        disabled={verifyTOTP.isPending || completeMFA.isPending}
                                        className="w-full"
                                    >
                                        {verifyTOTP.isPending || completeMFA.isPending
                                            ? "Verifying..."
                                            : "Verify and continue"}
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}

                    {mfaEnabled && (
                        <div className="space-y-4">
                            {duoAvailable && (
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

                            {(showCodeEntry || !duoAvailable) && (
                                <>
                                    <div className="space-y-2">
                                        <Label htmlFor="challenge-code">
                                            Authenticator or recovery code
                                        </Label>
                                        <Input
                                            id="challenge-code"
                                            placeholder="123456 or recovery code"
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

                            {duoAvailable && !showCodeEntry && (
                                <Button
                                    variant="ghost"
                                    onClick={() => setShowCodeEntry(true)}
                                    className="w-full"
                                >
                                    Use authenticator / recovery code instead
                                </Button>
                            )}

                            {!totpEnabled && duoEnrolled && (
                                <p className="text-xs text-muted-foreground text-center">
                                    Duo verification is enabled for your account.
                                </p>
                            )}
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
