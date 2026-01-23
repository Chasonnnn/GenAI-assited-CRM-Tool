"use client"

import { useState } from "react"
import Link from "next/link"
import { AlertCircle, ChevronDown, ChevronUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    Empty,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
    EmptyDescription,
} from "@/components/ui/empty"

interface ErrorStateProps {
    error: Error & { digest?: string }
    reset: () => void
    showDetails?: boolean
    secondaryHref?: string
    secondaryLabel?: string
}

/**
 * Reusable error state component with retry functionality.
 *
 * Shows a friendly error message with a "Try again" button.
 * In development, shows collapsible error details.
 */
export function ErrorState({
    error,
    reset,
    showDetails,
    secondaryHref,
    secondaryLabel = "Go to Dashboard",
}: ErrorStateProps) {
    const isDev = process.env.NODE_ENV === "development"
    const shouldShowDetails = showDetails ?? isDev
    const [isOpen, setIsOpen] = useState(false)

    return (
        <div className="flex min-h-[50vh] items-center justify-center p-6">
            <Empty>
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <AlertCircle className="size-6 text-destructive" />
                    </EmptyMedia>
                    <EmptyTitle>Something went wrong</EmptyTitle>
                    <EmptyDescription>
                        We encountered an unexpected error. Please try again.
                    </EmptyDescription>
                </EmptyHeader>

                <div className="flex items-center gap-2">
                    <Button onClick={reset}>Try again</Button>
                    {secondaryHref && (
                        <Button variant="outline" asChild>
                            <Link href={secondaryHref}>{secondaryLabel}</Link>
                        </Button>
                    )}
                </div>

                {shouldShowDetails && (
                    <div className="w-full max-w-md">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="mx-auto flex gap-1 text-muted-foreground"
                            onClick={() => setIsOpen(!isOpen)}
                        >
                            <span>Error details</span>
                            {isOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                        </Button>
                        {isOpen && (
                            <div className="mt-2 rounded-lg border bg-muted/50 p-4 text-left font-mono text-xs">
                                <p className="font-semibold text-destructive">
                                    {error.name}: {error.message}
                                </p>
                                {error.digest && (
                                    <p className="mt-1 text-muted-foreground">
                                        Digest: {error.digest}
                                    </p>
                                )}
                                {error.stack && (
                                    <pre className="mt-2 overflow-auto whitespace-pre-wrap text-muted-foreground">
                                        {error.stack}
                                    </pre>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </Empty>
        </div>
    )
}
