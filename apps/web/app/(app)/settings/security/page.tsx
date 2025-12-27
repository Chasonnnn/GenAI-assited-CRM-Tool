"use client"

/**
 * Security Settings Page - MFA enrollment and management.
 * 
 * Features:
 * - MFA status display
 * - TOTP setup with QR code
 * - Recovery codes display
 * - MFA disable option
 */

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog"
import {
    Alert,
    AlertDescription,
    AlertTitle,
} from "@/components/ui/alert"
import {
    ShieldCheckIcon,
    ShieldAlertIcon,
    SmartphoneIcon,
    KeyIcon,
    CopyIcon,
    CheckIcon,
    LoaderIcon,
    AlertTriangleIcon,
    RefreshCwIcon,
} from "lucide-react"
import {
    useMFAStatus,
    useSetupTOTP,
    useVerifyTOTPSetup,
    useRegenerateRecoveryCodes,
    useDisableMFA,
} from "@/lib/hooks/use-mfa"

// =============================================================================
// QR Code Component (using external library via script or simple display)
// =============================================================================

function QRCodeDisplay({ data }: { data: string }) {
    // Use a simple QR code image service for display
    // In production, you'd use a library like qrcode.react
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
                        <KeyIcon className="size-5" />
                        Recovery Codes
                    </DialogTitle>
                    <DialogDescription>
                        Save these codes in a secure location. Each code can only be used once.
                    </DialogDescription>
                </DialogHeader>

                <Alert variant="destructive" className="my-4">
                    <AlertTriangleIcon className="size-4" />
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
                                <CheckIcon className="size-4 mr-2" />
                                Copied!
                            </>
                        ) : (
                            <>
                                <CopyIcon className="size-4 mr-2" />
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

    const [showSetupDialog, setShowSetupDialog] = useState(false)
    const [showDisableDialog, setShowDisableDialog] = useState(false)
    const [showRecoveryCodes, setShowRecoveryCodes] = useState<string[] | null>(null)

    const [verificationCode, setVerificationCode] = useState("")
    const [setupData, setSetupData] = useState<{ secret: string; provisioning_uri: string } | null>(null)

    const setupTOTP = useSetupTOTP()
    const verifyTOTP = useVerifyTOTPSetup()
    const regenerateCodes = useRegenerateRecoveryCodes()
    const disableMFA = useDisableMFA()

    const handleStartSetup = async () => {
        setShowSetupDialog(true)
        try {
            const data = await setupTOTP.mutateAsync()
            setSetupData(data)
        } catch (error) {
            console.error("Failed to start TOTP setup:", error)
        }
    }

    const handleVerifyCode = async () => {
        if (!verificationCode) return

        try {
            const result = await verifyTOTP.mutateAsync(verificationCode)
            if (result.success) {
                setShowSetupDialog(false)
                setSetupData(null)
                setVerificationCode("")
                setShowRecoveryCodes(result.recovery_codes)
            }
        } catch (error) {
            console.error("Verification failed:", error)
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
                <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    const mfaEnabled = mfaStatus?.mfa_enabled || false
    const totpEnabled = mfaStatus?.totp_enabled || false
    const recoveryCodesRemaining = mfaStatus?.recovery_codes_remaining || 0

    return (
        <div className="container max-w-2xl py-8 space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Security Settings</h1>
                <p className="text-muted-foreground">
                    Manage your account security and two-factor authentication.
                </p>
            </div>

            {/* MFA Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        {mfaEnabled ? (
                            <>
                                <ShieldCheckIcon className="size-5 text-green-500" />
                                Two-Factor Authentication
                            </>
                        ) : (
                            <>
                                <ShieldAlertIcon className="size-5 text-amber-500" />
                                Two-Factor Authentication
                            </>
                        )}
                    </CardTitle>
                    <CardDescription>
                        {mfaEnabled
                            ? "Your account is protected with two-factor authentication."
                            : "Add an extra layer of security to your account."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {!mfaEnabled ? (
                        <>
                            <Alert>
                                <AlertTriangleIcon className="size-4" />
                                <AlertTitle>MFA Required</AlertTitle>
                                <AlertDescription>
                                    Two-factor authentication is required for all users.
                                    Please set up an authenticator app to continue.
                                </AlertDescription>
                            </Alert>
                            <Button onClick={handleStartSetup} disabled={setupTOTP.isPending}>
                                {setupTOTP.isPending ? (
                                    <>
                                        <LoaderIcon className="size-4 mr-2 animate-spin" />
                                        Setting up...
                                    </>
                                ) : (
                                    <>
                                        <SmartphoneIcon className="size-4 mr-2" />
                                        Set Up Authenticator App
                                    </>
                                )}
                            </Button>
                        </>
                    ) : (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                                <div className="flex items-center gap-3">
                                    <SmartphoneIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="font-medium">Authenticator App</p>
                                        <p className="text-sm text-muted-foreground">
                                            {totpEnabled ? "Enabled" : "Not configured"}
                                        </p>
                                    </div>
                                </div>
                                <Badge variant={totpEnabled ? "default" : "secondary"}>
                                    {totpEnabled ? "Active" : "Inactive"}
                                </Badge>
                            </div>

                            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                                <div className="flex items-center gap-3">
                                    <KeyIcon className="size-5 text-muted-foreground" />
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
                                >
                                    {regenerateCodes.isPending ? (
                                        <LoaderIcon className="size-4 animate-spin" />
                                    ) : (
                                        <>
                                            <RefreshCwIcon className="size-4 mr-2" />
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

            {/* TOTP Setup Dialog */}
            <Dialog open={showSetupDialog} onOpenChange={setShowSetupDialog}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Set Up Authenticator App</DialogTitle>
                        <DialogDescription>
                            Scan this QR code with your authenticator app (Google Authenticator, Authy, 1Password, etc.)
                        </DialogDescription>
                    </DialogHeader>

                    {setupData ? (
                        <div className="space-y-4">
                            <QRCodeDisplay data={setupData.provisioning_uri} />

                            <div className="space-y-2">
                                <Label>Or enter this code manually:</Label>
                                <code className="block p-2 bg-muted rounded text-sm text-center break-all">
                                    {setupData.secret}
                                </code>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="verification-code">
                                    Enter the 6-digit code from your app:
                                </Label>
                                <Input
                                    id="verification-code"
                                    type="text"
                                    inputMode="numeric"
                                    pattern="[0-9]*"
                                    maxLength={6}
                                    placeholder="123456"
                                    value={verificationCode}
                                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
                                    className="text-center text-lg tracking-widest"
                                />
                            </div>

                            <Button
                                className="w-full"
                                onClick={handleVerifyCode}
                                disabled={verificationCode.length !== 6 || verifyTOTP.isPending}
                            >
                                {verifyTOTP.isPending ? (
                                    <>
                                        <LoaderIcon className="size-4 mr-2 animate-spin" />
                                        Verifying...
                                    </>
                                ) : (
                                    "Verify and Enable"
                                )}
                            </Button>

                            {verifyTOTP.isError && (
                                <p className="text-sm text-destructive text-center">
                                    Invalid code. Please try again.
                                </p>
                            )}
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-40">
                            <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* Disable MFA Confirmation Dialog */}
            <Dialog open={showDisableDialog} onOpenChange={setShowDisableDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Disable Two-Factor Authentication?</DialogTitle>
                        <DialogDescription>
                            This will remove the security protection from your account.
                            Since MFA is required, you will need to set it up again immediately.
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
                                    <LoaderIcon className="size-4 mr-2 animate-spin" />
                                    Disabling...
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
