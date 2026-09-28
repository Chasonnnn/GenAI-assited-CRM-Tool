"use client"

import type * as React from "react"
import { Loader2Icon } from "lucide-react"

import { LoadErrorState, PermissionDeniedState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"

type ListPageGateProps = {
    /** Page title, shown in the header while access is checked or denied. */
    title: string
    /** Permission key the list API requires. */
    permission: string
    /** Denied-state copy naming the missing permission. */
    deniedDescription: string
    /** Rendered only when allowed, so denied roles send no list requests. */
    children: React.ReactNode
}

/**
 * List page shell for the Intended Parents and Matches lists: header plus loading or denied
 * state until the viewer holds `permission`. Same flow as SettingsPageGate, but the denied
 * state links to Dashboard because the parent list is gated too.
 */
export function ListPageGate({ title, permission, deniedDescription, children }: ListPageGateProps) {
    const { isLoading, isError, retry, isRetrying, can } = usePermissionCheck()

    if (!isLoading && !isError && can(permission)) return <>{children}</>

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <PageHeader title={title} />
            {isLoading ? (
                <div className="flex items-center justify-center p-12" role="status" aria-label="Loading">
                    <Loader2Icon
                        className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none"
                        aria-hidden="true"
                    />
                </div>
            ) : isError ? (
                <LoadErrorState
                    title="Couldn't check your access"
                    onRetry={retry}
                    isRetrying={isRetrying}
                    headingLevel={2}
                />
            ) : (
                <PermissionDeniedState
                    description={deniedDescription}
                    secondaryHref="/dashboard"
                    headingLevel={2}
                />
            )}
        </div>
    )
}
