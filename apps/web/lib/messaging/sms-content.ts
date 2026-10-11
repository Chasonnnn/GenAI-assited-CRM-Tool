/** Text message length, opt-in confirmation content, and template version grouping. */

import type {
    MessagingTemplateVersion,
    TwilioMessagingPurpose,
    TwilioSettings,
} from "@/lib/api/twilio"

export const MAX_SMS_BODY_CHARACTERS = 1600

const GSM_BASIC =
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
const GSM_EXTENDED = "^{}\\[~]|€\f"

/** Characters and carrier segments, as GSM-7 when every character fits and UCS-2 otherwise. */
export function countSmsSegments(body: string): { characters: number; segments: number } {
    const characters = [...body].length
    if (!body) return { characters: 0, segments: 0 }
    let gsmUnits = 0
    let gsm = true
    for (const character of body) {
        if (GSM_BASIC.includes(character)) gsmUnits += 1
        else if (GSM_EXTENDED.includes(character)) gsmUnits += 2
        else {
            gsm = false
            break
        }
    }
    if (gsm) return { characters, segments: gsmUnits <= 160 ? 1 : Math.ceil(gsmUnits / 153) }
    const units = body.length
    return { characters, segments: units <= 70 ? 1 : Math.ceil(units / 67) }
}

const MESSAGE_DATA_RATES = /\b(?:message|msg)s?\s*(?:and|&)\s*data\s+rates?\s+may\s+apply\b/i
const FREQUENCY = /\bfreq(?:uency)?\b|\b\d+\s*(?:msgs?|messages?)\s*(?:\/|per\b)\s*(?:day|week|month|year)\b/i
const HELP = /\bHELP\b/i
const STOP = /\bSTOP\b/i

function normalizedSpaces(value: string): string {
    return value.toLocaleLowerCase().split(/\s+/).filter(Boolean).join(" ")
}

export interface OptInRequirement {
    label: string
    met: boolean
}

/** The content publishing checks for an opt-in confirmation (CTIA 5.1.2.1 plus the brand). */
export function optInRequirements(
    body: string,
    settings: Pick<TwilioSettings, "legal_messaging_brand" | "expected_frequency" | "support_contact"> | null,
): OptInRequirement[] {
    const normalizedBody = normalizedSpaces(body)
    const contains = (value: string | null | undefined) => {
        const normalized = normalizedSpaces(value ?? "")
        return Boolean(normalized) && normalizedBody.includes(normalized)
    }
    return [
        { label: "Brand name", met: contains(settings?.legal_messaging_brand) },
        {
            label: "Message frequency",
            met: contains(settings?.expected_frequency) || FREQUENCY.test(body),
        },
        { label: "Message and data rates", met: MESSAGE_DATA_RATES.test(body) },
        { label: "HELP or support contact", met: HELP.test(body) || contains(settings?.support_contact) },
        { label: "STOP instructions", met: STOP.test(body) },
    ]
}

/** Fill {{variable}} tokens with plain text, as the server does before sending. */
export function renderSmsBody(body: string, values: Record<string, string>): string {
    return body.replace(/{{\s*([a-zA-Z0-9_]+)\s*}}/g, (_match, name: string) => values[name] ?? "")
}

export interface TemplateFamily {
    key: string
    name: string
    purpose: TwilioMessagingPurpose
    isEnrollmentConfirmation: boolean
    /** Newest version first. */
    versions: MessagingTemplateVersion[]
    latest: MessagingTemplateVersion
    live: MessagingTemplateVersion | null
    /** The latest version while it is a draft. */
    draft: MessagingTemplateVersion | null
}

export function groupTemplateFamilies(versions: MessagingTemplateVersion[]): TemplateFamily[] {
    const byKey = new Map<string, MessagingTemplateVersion[]>()
    for (const version of versions) {
        byKey.set(version.template_key, [...(byKey.get(version.template_key) ?? []), version])
    }
    const families: TemplateFamily[] = []
    for (const [key, familyVersions] of byKey) {
        const sorted = [...familyVersions].sort((left, right) => right.version - left.version)
        const latest = sorted[0]!
        families.push({
            key,
            name: latest.name,
            purpose: latest.purpose,
            isEnrollmentConfirmation: latest.is_enrollment_confirmation,
            versions: sorted,
            latest,
            live: sorted.find((version) => version.status === "published") ?? null,
            draft: latest.status === "draft" ? latest : null,
        })
    }
    return families.sort((left, right) => right.latest.created_at.localeCompare(left.latest.created_at))
}

export const PURPOSE_LABELS: Record<TwilioMessagingPurpose, string> = {
    operational: "Operational",
    promotional: "Promotional",
}
