"use client"

import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
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

/**
 * Session expiration detection dialog.
 *
 * Subscribes to TanStack Query cache events and detects 401 errors,
 * which indicate the user's session has expired. Shows a modal dialog
 * prompting the user to log in again.
 */
export function SessionExpiredDialog() {
    const [isExpired, setIsExpired] = useState(false)
    const queryClient = useQueryClient()

    useEffect(() => {
        const queryCache = queryClient.getQueryCache()
        const mutationCache = queryClient.getMutationCache()

        // Check if an error is a 401 response
        const is401Error = (error: unknown): boolean => {
            if (!error || typeof error !== "object") return false
            // Check for status property (fetch Response-like errors)
            if ("status" in error && error.status === 401) return true
            // Check for response.status (axios-like errors)
            if (
                "response" in error &&
                error.response &&
                typeof error.response === "object" &&
                "status" in error.response &&
                error.response.status === 401
            ) {
                return true
            }
            return false
        }

        // Subscribe to query cache events
        const unsubscribeQueries = queryCache.subscribe((event) => {
            if (
                event.type === "updated" &&
                event.action.type === "error" &&
                is401Error(event.action.error)
            ) {
                setIsExpired(true)
            }
        })

        // Subscribe to mutation cache events
        const unsubscribeMutations = mutationCache.subscribe((event) => {
            if (
                event.type === "updated" &&
                event.action.type === "error" &&
                is401Error(event.action.error)
            ) {
                setIsExpired(true)
            }
        })

        return () => {
            unsubscribeQueries()
            unsubscribeMutations()
        }
    }, [queryClient])

    const handleLogin = () => {
        // Redirect to login page
        window.location.href = "/login"
    }

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
                    <AlertDialogAction onClick={handleLogin}>
                        Log in again
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}
