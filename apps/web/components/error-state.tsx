"use client"

import { useEffect, useState } from "react"
import Link from "@/components/app-link"
import { AlertCircle, ArrowLeftIcon, ChevronDown, Loader2Icon, SearchXIcon, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import {
    Empty,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
    EmptyDescription,
    type EmptyTitleHeadingLevel,
} from "@/components/ui/empty"
import { cn } from "@/lib/utils"
import { reportClientError } from "@/lib/client-error-telemetry"
import { getQueryErrorKind } from "@/lib/error-utils"

interface ErrorStateProps {
    error: Error & { digest?: string }
    reset: () => void
    showDetails?: boolean
    secondaryHref?: string
    secondaryLabel?: string
}

interface PermissionDeniedStateProps {
    title?: string | undefined
    description: string
    onRetry?: (() => void) | undefined
    secondaryHref?: string | undefined
    secondaryLabel?: string | undefined
    /** Heading semantics for the title. Pass 1 when the state replaces the whole page, including its header. */
    headingLevel?: EmptyTitleHeadingLevel | undefined
    className?: string | undefined
}

interface LoadErrorStateProps {
    /** Names what failed, for example "Couldn't load alerts". */
    title: string
    onRetry: () => void
    /** Pass query.isFetching: a failed query keeps isError while it refetches, so the state stays mounted. */
    isRetrying?: boolean | undefined
    /** Heading semantics for the title. Pass 1 when the state replaces the whole page, including its header. */
    headingLevel?: EmptyTitleHeadingLevel | undefined
    className?: string | undefined
}

interface NotFoundStateProps {
    /** Names the missing record, for example "Surrogate not found". */
    title: string
    backHref: string
    backLabel: string
    /** Heading semantics for the title. Pass 1 when the state replaces the whole page, including its header. */
    headingLevel?: EmptyTitleHeadingLevel | undefined
    className?: string | undefined
}

interface QueryErrorStateProps {
    error: unknown
    onRetry: () => void
    /** Load-error title for any failure that is not a handled 403 or 404. */
    title: string
    isRetrying?: boolean | undefined
    /** Denied-state copy for a 403. Without it a generic denied state renders. */
    forbidden?: Omit<PermissionDeniedStateProps, "className" | "headingLevel"> | undefined
    /** Record routes only: a 404, or a 422 from a malformed id, renders this not-found state. */
    notFound?: Omit<NotFoundStateProps, "className" | "headingLevel"> | undefined
    /** Heading semantics for the title. Pass 1 when the state replaces the whole page, including its header. */
    headingLevel?: EmptyTitleHeadingLevel | undefined
    className?: string | undefined
}

const STATE_FRAME_CLASS = "flex min-h-[18rem] items-center justify-center p-6"

function useReportErrorBoundary(error: Error): void {
    useEffect(() => {
        reportClientError("react_error_boundary", error)
    }, [error])
}

/**
 * Route error boundary state with retry functionality.
 *
 * Shows a friendly error message with a "Try again" button.
 * In development, shows collapsible error details.
 * For failed queries, use LoadErrorState or QueryErrorState instead.
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
    useReportErrorBoundary(error)

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
                        <Link
                            href={secondaryHref}
                            className={buttonVariants({ variant: "outline" })}
                        >
                            {secondaryLabel}
                        </Link>
                    )}
                </div>

                {shouldShowDetails && (
                    <div className="w-full max-w-md">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="mx-auto flex gap-1 text-muted-foreground"
                            onClick={() => setIsOpen(!isOpen)}
                            aria-expanded={isOpen}
                        >
                            <span>Error details</span>
                            <ChevronDown
                                className={cn("size-4 transition-transform duration-200 ease-smooth-out", isOpen && "rotate-180")}
                                aria-hidden="true"
                            />
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

export function PermissionDeniedState({
    title = "Permission required",
    description,
    onRetry,
    secondaryHref,
    secondaryLabel = "Go to Dashboard",
    headingLevel,
    className,
}: PermissionDeniedStateProps) {
    return (
        <div data-slot="permission-denied-state" className={cn(STATE_FRAME_CLASS, className)}>
            <Empty>
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <ShieldAlert className="size-6 text-warning" aria-hidden="true" />
                    </EmptyMedia>
                    <EmptyTitle headingLevel={headingLevel}>{title}</EmptyTitle>
                    <EmptyDescription>{description}</EmptyDescription>
                </EmptyHeader>

                {(onRetry || secondaryHref) && (
                    <div className="flex items-center gap-2">
                        {onRetry && (
                            <Button variant="outline" onClick={onRetry}>
                                Try again
                            </Button>
                        )}
                        {secondaryHref && (
                            <Link
                                href={secondaryHref}
                                className={buttonVariants({ variant: "outline" })}
                            >
                                {secondaryLabel}
                            </Link>
                        )}
                    </div>
                )}
            </Empty>
        </div>
    )
}

/** A query failed. Never shows the raw error message; the title says what did not load. */
export function LoadErrorState({
    title,
    onRetry,
    isRetrying = false,
    headingLevel,
    className,
}: LoadErrorStateProps) {
    return (
        <div data-slot="load-error-state" className={cn(STATE_FRAME_CLASS, className)}>
            <Empty>
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <AlertCircle className="size-6 text-destructive" aria-hidden="true" />
                    </EmptyMedia>
                    <EmptyTitle headingLevel={headingLevel}>{title}</EmptyTitle>
                </EmptyHeader>
                {/* Stays focusable while disabled so keyboard focus is not dropped during the retry. */}
                <Button onClick={onRetry} disabled={isRetrying} focusableWhenDisabled>
                    {isRetrying ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : null}
                    Try again
                </Button>
            </Empty>
        </div>
    )
}

export function NotFoundState({ title, backHref, backLabel, headingLevel, className }: NotFoundStateProps) {
    return (
        <div data-slot="not-found-state" className={cn(STATE_FRAME_CLASS, className)}>
            <Empty>
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <SearchXIcon aria-hidden="true" />
                    </EmptyMedia>
                    <EmptyTitle headingLevel={headingLevel}>{title}</EmptyTitle>
                </EmptyHeader>
                <Link href={backHref} className={buttonVariants({ variant: "outline" })}>
                    <ArrowLeftIcon aria-hidden="true" />
                    {backLabel}
                </Link>
            </Empty>
        </div>
    )
}

/**
 * Renders the right state for a failed query: 403 → PermissionDeniedState,
 * 404 (with `notFound`) → NotFoundState, anything else → LoadErrorState with retry.
 */
export function QueryErrorState({
    error,
    onRetry,
    title,
    isRetrying,
    forbidden,
    notFound,
    headingLevel,
    className,
}: QueryErrorStateProps) {
    const kind = getQueryErrorKind(error, { includeInvalidId: notFound !== undefined })

    if (kind === "forbidden") {
        return (
            <PermissionDeniedState
                description="Ask an admin to update your role."
                {...forbidden}
                headingLevel={headingLevel}
                className={className}
            />
        )
    }

    if (kind === "not_found" && notFound) {
        return <NotFoundState {...notFound} headingLevel={headingLevel} className={className} />
    }

    return (
        <LoadErrorState
            title={title}
            onRetry={onRetry}
            isRetrying={isRetrying}
            headingLevel={headingLevel}
            className={className}
        />
    )
}
