"use client"

import { Clock } from "lucide-react"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogMedia,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useSessionExpirationDetection } from "@/lib/hooks/use-session-expiration-detection"

function redirectToLogin() {
    window.location.href = "/login"
}

/**
 * Session expiration detection dialog.
 *
 * Subscribes to TanStack Query cache events and detects 401 errors,
 * which indicate the user's session has expired. Shows a modal dialog
 * prompting the user to log in again.
 */
export function SessionExpiredDialog() {
    const isExpired = useSessionExpirationDetection()

    return (
        <AlertDialog open={isExpired}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogMedia className="bg-amber-500/10">
                        <Clock className="size-8 text-amber-600" />
                    </AlertDialogMedia>
                    <AlertDialogTitle>Session Expired</AlertDialogTitle>
                    <AlertDialogDescription>
                        Your session has expired due to inactivity. Please log
                        in again to continue.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogAction onClick={redirectToLogin}>
                        Log in again
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}
