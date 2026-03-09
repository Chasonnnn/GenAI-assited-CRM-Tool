"use client"

/**
 * Security Settings Page - Duo MFA enrollment and recovery management.
 *
 * Features:
 * - MFA status display
 * - Duo setup / verification handoff
 * - Recovery codes display
 * - MFA disable option
 */

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Dialog,
    DialogFooter,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Alert,
    AlertDescription,
    AlertTitle,
} from "@/components/ui/alert"
import {
    AlertTriangleIcon,
    CheckIcon,
    CopyIcon,
    KeyIcon,
    Loader2Icon,
    RefreshCwIcon,
    ShieldAlertIcon,
    ShieldCheckIcon,
} from "lucide-react"
import {
    useDisableMFA,
    useDuoStatus,
    useInitiateDuoAuth,
    useMFAStatus,
    useRegenerateRecoveryCodes,
} from "@/lib/hooks/use-mfa"

// =============================================================================
// Recovery Codes Display
// =============================================================================

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
                        <KeyIcon className="size-5" aria-hidden="true" />
                        Recovery Codes
                    </DialogTitle>
                    <DialogDescription>
                        Save these codes in a secure location. Each code can only be used once.
                    </DialogDescription>
                </DialogHeader>

                <Alert variant="destructive" className="my-4">
                    <AlertTriangleIcon className="size-4" aria-hidden="true" />
                    <AlertTitle>Important</AlertTitle>
                    <AlertDescription>
                        These codes will not be shown again. Save them now!
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
                                <CheckIcon className="size-4 mr-2" aria-hidden="true" />
                                Copied!
                            </>
                        ) : (
                            <>
                                <CopyIcon className="size-4 mr-2" aria-hidden="true" />
                                Copy All
                            </>
                        )}
                    </Button>
                    <Button onClick={onClose}>I've Saved These Codes</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// =============================================================================
// Main Component
// =============================================================================

export default function SecuritySettingsPage() {
    const { data: mfaStatus, isLoading: statusLoading } = useMFAStatus()
    const { data: duoStatus } = useDuoStatus()

    const [showDisableDialog, setShowDisableDialog] = useState(false)
    const [showRecoveryCodes, setShowRecoveryCodes] = useState<string[] | null>(null)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

    const initiateDuo = useInitiateDuoAuth()
    const regenerateCodes = useRegenerateRecoveryCodes()
    const disableMFA = useDisableMFA()

    const handleStartDuo = async () => {
        setErrorMessage(null)
        try {
            const result = await initiateDuo.mutateAsync("app")
            window.location.assign(result.auth_url)
        } catch (error) {
            console.error("Failed to start Duo setup:", error)
            setErrorMessage("Unable to start Duo setup. Please try again.")
        }
    }

    const handleRegenerateCodes = async () => {
        try {
            const result = await regenerateCodes.mutateAsync()
            setShowRecoveryCodes(result.codes)
        } catch (error) {
            console.error("Failed to regenerate codes:", error)
        }
    }

    const handleDisableMFA = async () => {
        try {
            await disableMFA.mutateAsync()
            setShowDisableDialog(false)
        } catch (error) {
            console.error("Failed to disable MFA:", error)
        }
    }

    if (statusLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    const mfaEnabled = mfaStatus?.mfa_enabled || false
    const recoveryCodesRemaining = mfaStatus?.recovery_codes_remaining || 0
    const duoAvailable = duoStatus?.available || false
    const duoEnrolled = duoStatus?.enrolled || false

    return (
        <div className="container max-w-2xl py-8 space-y-6">
            <div>
                <h1 className="text-2xl font-semibold">Security Settings</h1>
                <p className="text-muted-foreground">
                    Manage your Duo enrollment and account recovery settings.
                </p>
            </div>

            {/* MFA Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        {mfaEnabled ? (
                            <>
                                <ShieldCheckIcon className="size-5 text-green-500" aria-hidden="true" />
                                Two-Factor Authentication
                            </>
                        ) : (
                            <>
                                <ShieldAlertIcon className="size-5 text-amber-500" aria-hidden="true" />
                                Two-Factor Authentication
                            </>
                        )}
                    </CardTitle>
                    <CardDescription>
                        {mfaEnabled
                            ? "Your account is protected with two-factor authentication."
                            : "Set up Duo to finish enabling two-factor authentication."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {errorMessage && (
                        <Alert variant="destructive">
                            <AlertTriangleIcon className="size-4" aria-hidden="true" />
                            <AlertTitle>Action needed</AlertTitle>
                            <AlertDescription>{errorMessage}</AlertDescription>
                        </Alert>
                    )}

                    {!mfaEnabled ? (
                        <>
                            <Alert variant={duoAvailable ? "default" : "destructive"}>
                                <AlertTriangleIcon className="size-4" aria-hidden="true" />
                                <AlertTitle>{duoAvailable ? "Duo Required" : "Duo Unavailable"}</AlertTitle>
                                <AlertDescription>
                                    {duoAvailable
                                        ? "Two-factor authentication is required for all users. Please set up Duo to continue."
                                        : "Duo is temporarily unavailable. Please try again later or contact support."}
                                </AlertDescription>
                            </Alert>
                            <Button onClick={handleStartDuo} disabled={initiateDuo.isPending || !duoAvailable}>
                                {initiateDuo.isPending ? (
                                    <>
                                        <Loader2Icon className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        Starting Duo…
                                    </>
                                ) : (
                                    "Set Up Duo"
                                )}
                            </Button>
                        </>
                    ) : (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                                <div className="flex items-center gap-3">
                                    <ShieldCheckIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                                    <div>
                                        <p className="font-medium">Duo Security</p>
                                        <p className="text-sm text-muted-foreground">
                                            {duoEnrolled ? "Configured" : "Setup required"}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <Badge variant={duoEnrolled ? "default" : "secondary"}>
                                        {duoEnrolled ? "Active" : "Pending"}
                                    </Badge>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleStartDuo}
                                        disabled={initiateDuo.isPending || !duoAvailable}
                                    >
                                        {initiateDuo.isPending
                                            ? "Starting Duo…"
                                            : duoEnrolled
                                              ? "Continue with Duo"
                                              : "Set Up Duo"}
                                    </Button>
                                </div>
                            </div>

                            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                                <div className="flex items-center gap-3">
                                    <KeyIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                                    <div>
                                        <p className="font-medium">Recovery Codes</p>
                                        <p className="text-sm text-muted-foreground">
                                            {recoveryCodesRemaining} codes remaining
                                        </p>
                                    </div>
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleRegenerateCodes}
                                    disabled={regenerateCodes.isPending}
                                    aria-label="Regenerate recovery codes"
                                >
                                    {regenerateCodes.isPending ? (
                                        <>
                                            <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                            <span className="sr-only">Regenerating</span>
                                        </>
                                    ) : (
                                        <>
                                            <RefreshCwIcon className="size-4 mr-2" aria-hidden="true" />
                                            Regenerate
                                        </>
                                    )}
                                </Button>
                            </div>

                            <div className="pt-4 border-t">
                                <Button
                                    variant="destructive"
                                    onClick={() => setShowDisableDialog(true)}
                                >
                                    Disable Two-Factor Authentication
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Disable MFA Confirmation Dialog */}
            <Dialog open={showDisableDialog} onOpenChange={setShowDisableDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Disable Two-Factor Authentication?</DialogTitle>
                        <DialogDescription>
                            This will remove the security protection from your account.
                            Since MFA is required, you will need to set up Duo again immediately.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowDisableDialog(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleDisableMFA}
                            disabled={disableMFA.isPending}
                        >
                            {disableMFA.isPending ? (
                                <>
                                    <Loader2Icon className="size-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Disabling…
                                </>
                            ) : (
                                "Disable MFA"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Recovery Codes Display */}
            {showRecoveryCodes && (
                <RecoveryCodesDisplay
                    codes={showRecoveryCodes}
                    onClose={() => setShowRecoveryCodes(null)}
                />
            )}
        </div>
    )
}
