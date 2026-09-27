"use client"

import type { ReactNode } from "react"
import { InfoIcon } from "lucide-react"

import Link from "@/components/app-link"
import { Alert, AlertAction, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

export type AiUnavailableReason = "org_disabled" | "no_permission" | "no_api_key"

const AI_UNAVAILABLE_MESSAGES: Record<AiUnavailableReason, string> = {
    org_disabled: "AI is turned off for this organization.",
    no_permission: "Your role does not include AI access.",
    no_api_key: "AI needs an API key before it can generate.",
}

export function getAiUnavailableMessage(reason: AiUnavailableReason): string {
    return AI_UNAVAILABLE_MESSAGES[reason]
}

/** The org switch wins over the role check: an admin cannot fix a role while AI is off. */
export function getAiUnavailableReason({
    aiEnabled,
    canUseAI,
}: {
    aiEnabled: boolean
    canUseAI: boolean
}): AiUnavailableReason | null {
    if (!aiEnabled) return "org_disabled"
    if (!canUseAI) return "no_permission"
    return null
}

/**
 * One-line notice for pages whose AI features are unavailable. Pages disable their
 * AI inputs while it shows. `action` replaces the default settings link.
 */
export function AiUnavailableNotice({
    reason,
    canManageSettings = false,
    action,
    className,
}: {
    reason: AiUnavailableReason
    /** Shows a link to the organization AI settings when AI is off. */
    canManageSettings?: boolean
    action?: ReactNode
    className?: string
}) {
    const settingsAction =
        action ??
        (canManageSettings && reason === "org_disabled" ? (
            <Button variant="outline" size="sm" render={<Link href="/settings/integrations" />}>
                AI settings
            </Button>
        ) : null)

    return (
        <Alert role="status" className={className}>
            <InfoIcon aria-hidden="true" />
            <AlertTitle className="leading-6">{AI_UNAVAILABLE_MESSAGES[reason]}</AlertTitle>
            {settingsAction ? <AlertAction>{settingsAction}</AlertAction> : null}
        </Alert>
    )
}
