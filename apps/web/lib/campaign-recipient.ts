import type { CampaignRecipientType } from "@/lib/api/campaigns"
import type { PipelineEntityType } from "@/lib/api/pipelines"

export const CAMPAIGN_RECIPIENT_OPTIONS: Array<{
    value: CampaignRecipientType
    label: string
}> = [
    { value: "case", label: "Surrogates" },
    { value: "intended_parent", label: "Intended Parents" },
    { value: "egg_donor", label: "Egg Donors" },
    { value: "sperm_donor", label: "Sperm Donors" },
]

const CAMPAIGN_RECIPIENT_LABELS: Record<CampaignRecipientType, string> =
    Object.fromEntries(
        CAMPAIGN_RECIPIENT_OPTIONS.map((option) => [option.value, option.label]),
    ) as Record<CampaignRecipientType, string>

export function isCampaignRecipientType(value: string | null): value is CampaignRecipientType {
    return CAMPAIGN_RECIPIENT_OPTIONS.some((option) => option.value === value)
}

export function isDonorCampaignRecipientType(
    value: CampaignRecipientType,
): value is Extract<CampaignRecipientType, "egg_donor" | "sperm_donor"> {
    return value === "egg_donor" || value === "sperm_donor"
}

export function getCampaignRecipientLabel(value: CampaignRecipientType): string {
    return CAMPAIGN_RECIPIENT_LABELS[value]
}

/** Title for a send confirmation. The count is unknown (null) while the recipient preview loads. */
export function getCampaignSendConfirmTitle(recipientCount: number | null | undefined): string {
    if (recipientCount === null || recipientCount === undefined) return "Send campaign now?"
    const noun = recipientCount === 1 ? "recipient" : "recipients"
    return `Send to ${recipientCount.toLocaleString()} ${noun} now?`
}

export function getCampaignPipelineEntityType(
    value: CampaignRecipientType,
): PipelineEntityType | null {
    if (value === "intended_parent") return null
    if (value === "case") return "surrogate"
    return value
}

export function getCampaignRecipientHref(
    entityType: string,
    entityId: string,
): string | undefined {
    if (entityType === "egg_donor" || entityType === "sperm_donor") {
        return `/donors/${entityId}`
    }
    return undefined
}
