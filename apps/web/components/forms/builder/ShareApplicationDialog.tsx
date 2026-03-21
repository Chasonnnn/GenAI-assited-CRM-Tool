"use client"

import { DownloadIcon, LinkIcon, QrCodeIcon } from "lucide-react"

import {
    AlertDialog,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import type { FormIntakeLinkRead } from "@/lib/api/forms"

type ShareApplicationDialogProps = {
    open: boolean
    selectedQrLink: FormIntakeLinkRead | null
    onOpenChange: (open: boolean) => void
    onCopyLink: (link: FormIntakeLinkRead) => Promise<void>
    onDownloadQrSvg: () => void
    onDownloadQrPng: () => Promise<void>
}

export function ShareApplicationDialog({
    open,
    selectedQrLink,
    onOpenChange,
    onCopyLink,
    onDownloadQrSvg,
    onDownloadQrPng,
}: ShareApplicationDialogProps) {
    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Share Application Intake</AlertDialogTitle>
                    <AlertDialogDescription>
                        Choose how you want to distribute this published application form.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                {selectedQrLink?.intake_url ? (
                    <div className="space-y-2 rounded-md border border-stone-200 bg-stone-50 p-3 text-xs text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                        <div className="font-medium text-stone-900 dark:text-stone-100">
                            {selectedQrLink.event_name || selectedQrLink.campaign_name || "Shared intake link"}
                        </div>
                        <div className="break-all">{selectedQrLink.intake_url}</div>
                    </div>
                ) : (
                    <p className="text-sm text-stone-500">
                        No shared intake link is available yet.
                    </p>
                )}
                <AlertDialogFooter>
                    <AlertDialogCancel>Close</AlertDialogCancel>
                    <Button
                        type="button"
                        variant="outline"
                        disabled={!selectedQrLink}
                        onClick={async () => {
                            if (!selectedQrLink) return
                            await onCopyLink(selectedQrLink)
                            onOpenChange(false)
                        }}
                    >
                        <LinkIcon className="mr-2 size-4" />
                        Copy Link
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        disabled={!selectedQrLink}
                        onClick={() => {
                            if (!selectedQrLink) return
                            onDownloadQrSvg()
                            onOpenChange(false)
                        }}
                    >
                        <DownloadIcon className="mr-2 size-4" />
                        QR (SVG)
                    </Button>
                    <Button
                        type="button"
                        disabled={!selectedQrLink}
                        onClick={() => {
                            if (!selectedQrLink) return
                            void onDownloadQrPng()
                            onOpenChange(false)
                        }}
                    >
                        <QrCodeIcon className="mr-2 size-4" />
                        QR (PNG)
                    </Button>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}
