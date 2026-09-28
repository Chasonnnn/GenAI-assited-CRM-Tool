"use client"

import type * as React from "react"
import { Loader2Icon } from "lucide-react"

import { LoadErrorState, PermissionDeniedState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"

type SettingsPageGateProps = {
    /** Page title, shown in the header while access is checked or denied. */
    title: string
    /** Permission key the page's API routes require. */
    permission: string
    /** Denied-state copy naming the missing permission. */
    deniedDescription: string
    back?: { href: string; label: string } | undefined
    /** Rendered only when allowed, so denied roles send no requests for the page's data. */
    children: React.ReactNode
}

/** Settings page shell: header plus loading or denied state until the viewer holds `permission`. */
export function SettingsPageGate({ title, permission, deniedDescription, back, children }: SettingsPageGateProps) {
    const { isLoading, isError, retry, isRetrying, can } = usePermissionCheck()

    if (!isLoading && can(permission)) return <>{children}</>

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader title={title} back={back} />
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
                    secondaryHref="/settings"
                    secondaryLabel="Back to Settings"
                    headingLevel={2}
                />
            )}
        </div>
    )
}
