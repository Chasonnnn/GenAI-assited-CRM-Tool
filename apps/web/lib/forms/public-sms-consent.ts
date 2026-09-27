import type { FormField, MessagingConsentOptionsRead } from "@/lib/api/forms"
import {
    isEmptyPublicFieldValue,
    isValidPublicPhone,
    type PublicFieldValue,
} from "@/lib/forms/public-field-validation"

export type SmsConsentPurpose = "operational" | "promotional"
export type SmsConsentSelection = Record<SmsConsentPurpose, boolean>

export const SMS_CONSENT_PURPOSES: readonly SmsConsentPurpose[] = ["operational", "promotional"]

function hasSelectedSmsConsent(
    options: MessagingConsentOptionsRead | null | undefined,
    selection: SmsConsentSelection,
): boolean {
    return SMS_CONSENT_PURPOSES.some((purpose) => Boolean(options?.[purpose]) && selection[purpose])
}

/** The phone field key sent with checked consent; the server returns 409 if its resolved key differs. */
export function getSubmittedSmsPhoneFieldKey(
    options: MessagingConsentOptionsRead | null | undefined,
    selection: SmsConsentSelection,
): string | null {
    return hasSelectedSmsConsent(options, selection) ? options?.phone_field_key ?? null : null
}

export function resolveSmsConsentPhoneField(
    options: MessagingConsentOptionsRead | null | undefined,
    visibleFields: readonly FormField[],
): FormField | null {
    const phoneFieldKey = options?.phone_field_key
    if (!phoneFieldKey) return null
    return visibleFields.find((field) => field.key === phoneFieldKey) ?? null
}

/**
 * Returns the blocking error for a checked SMS consent. A null `phoneField` means the enrolled
 * phone field is hidden by conditional logic or not rendered, so there is no number to enroll.
 */
export function getSmsConsentError({
    options,
    selection,
    phoneField,
    phoneValue,
}: {
    options: MessagingConsentOptionsRead | null | undefined
    selection: SmsConsentSelection
    phoneField: FormField | null
    phoneValue: PublicFieldValue | undefined
}): string | null {
    if (!hasSelectedSmsConsent(options, selection)) return null
    if (!phoneField) {
        return "Add a phone number to receive text messages, or uncheck to continue."
    }
    if (isEmptyPublicFieldValue(phoneValue)) {
        return "Enter your phone number to receive text messages."
    }
    if (typeof phoneValue !== "string" || !isValidPublicPhone(phoneValue)) {
        return "Enter a valid phone number to receive text messages."
    }
    return null
}
