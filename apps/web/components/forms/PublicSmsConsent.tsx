"use client"

import type { Ref } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import type { MessagingConsentOptionsRead } from "@/lib/api/forms"
import {
    SMS_CONSENT_PURPOSES,
    type SmsConsentPurpose,
    type SmsConsentSelection,
} from "@/lib/forms/public-sms-consent"
import { cn } from "@/lib/utils"

const SMS_CONSENT_ERROR_ID = "sms-consent-error"
const smsConsentLinkClassName =
    "font-medium text-neutral-900 underline underline-offset-2 hover:text-primary"

interface PublicSmsConsentProps {
    options: MessagingConsentOptionsRead | null | undefined
    selection: SmsConsentSelection
    onCheckedChange: (purpose: SmsConsentPurpose, checked: boolean) => void
    error?: string | null
    density?: "default" | "compact"
    /** Attached to the first checked checkbox so callers can focus it on a consent error. */
    checkedCheckboxRef?: Ref<HTMLSpanElement>
}

export function PublicSmsConsent({
    options,
    selection,
    onCheckedChange,
    error,
    density = "default",
    checkedCheckboxRef,
}: PublicSmsConsentProps) {
    const available = SMS_CONSENT_PURPOSES.flatMap((purpose) => {
        const option = options?.[purpose]
        return option ? [{ purpose, option }] : []
    })
    if (available.length === 0) return null
    const firstCheckedPurpose = available.find(({ purpose }) => selection[purpose])?.purpose

    return (
        <div data-slot="public-sms-consent" className="space-y-2">
            {available.map(({ purpose, option }) => {
                const checkboxId = `sms-${purpose}`
                const isInvalid = Boolean(error) && selection[purpose]
                return (
                    <div
                        key={purpose}
                        className={cn(
                            "flex items-start gap-3 border bg-white",
                            density === "compact" ? "rounded-md p-3" : "rounded-lg p-4",
                            isInvalid ? "border-red-300" : "border-neutral-200",
                        )}
                    >
                        <Checkbox
                            ref={purpose === firstCheckedPurpose ? checkedCheckboxRef : undefined}
                            id={checkboxId}
                            checked={selection[purpose]}
                            onCheckedChange={(checked) => onCheckedChange(purpose, checked === true)}
                            aria-invalid={isInvalid || undefined}
                            aria-describedby={isInvalid ? SMS_CONSENT_ERROR_ID : undefined}
                            className="mt-1"
                        />
                        <div className="min-w-0 space-y-1">
                            <label htmlFor={checkboxId} className="block text-sm leading-6 text-neutral-700">
                                {option.disclosure}
                            </label>
                            <p className="text-sm leading-6 text-neutral-700">
                                <a
                                    href={option.sms_terms_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={smsConsentLinkClassName}
                                >
                                    Terms of Service
                                </a>
                                <span aria-hidden="true" className="mx-2 text-neutral-400">
                                    |
                                </span>
                                <a
                                    href={option.privacy_policy_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={smsConsentLinkClassName}
                                >
                                    Privacy Policy
                                </a>
                            </p>
                        </div>
                    </div>
                )
            })}
            {error ? (
                <p id={SMS_CONSENT_ERROR_ID} role="alert" className="text-sm leading-6 text-red-700">
                    {error}
                </p>
            ) : null}
        </div>
    )
}
