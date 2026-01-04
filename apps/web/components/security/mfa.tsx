"use client"

import { useState } from "react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { CopyIcon, CheckIcon, KeyIcon } from "lucide-react"

interface QRCodeDisplayProps {
    data: string
}

export function QRCodeDisplay({ data }: QRCodeDisplayProps) {
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

interface RecoveryCodesDialogProps {
    codes: string[]
    onClose: () => void
    alertDescription: string
    alertTitle?: string
    alertIcon?: ReactNode
    copyLabel?: string
    copiedLabel?: string
    confirmLabel?: string
}

export function RecoveryCodesDialog({
    codes,
    onClose,
    alertDescription,
    alertTitle = "Important",
    alertIcon,
    copyLabel = "Copy All",
    copiedLabel = "Copied",
    confirmLabel = "I've Saved These Codes",
}: RecoveryCodesDialogProps) {
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
                    {alertIcon}
                    <AlertTitle>{alertTitle}</AlertTitle>
                    <AlertDescription>{alertDescription}</AlertDescription>
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
                                {copiedLabel}
                            </>
                        ) : (
                            <>
                                <CopyIcon className="size-4 mr-2" />
                                {copyLabel}
                            </>
                        )}
                    </Button>
                    <Button onClick={onClose}>{confirmLabel}</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
