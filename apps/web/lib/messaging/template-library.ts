/** List-page helpers for the text message template library. */

import type { Route } from "next"

import type { MessagingTemplateUse, TwilioMessagingPurpose, TwilioReadiness } from "@/lib/api/twilio"
import type { TemplateFamily } from "@/lib/messaging/sms-content"

export interface TestTemplateOption {
    id: string
    label: string
    purpose: TwilioMessagingPurpose
}

export function templateHref(key: string): Route {
    return `/automation/message-templates/${key}` as Route
}

export function usageSummary(uses: MessagingTemplateUse[] | undefined): string | null {
    if (!uses?.length) return null
    const workflows = uses.filter((use) => use.kind === "workflow").length
    const campaigns = uses.length - workflows
    return [
        workflows ? `${workflows} workflow${workflows === 1 ? "" : "s"}` : null,
        campaigns ? `${campaigns} campaign${campaigns === 1 ? "" : "s"}` : null,
    ]
        .filter(Boolean)
        .join(" · ")
}

/** Test-send choices: the draft and the live version of each template. */
export function testTemplateOptions(families: TemplateFamily[]): TestTemplateOption[] {
    return families.flatMap((family) =>
        [family.draft, family.live]
            .filter((version) => version !== null)
            .map((version) => ({
                id: version.id,
                label: `${family.name} · ${version.status === "draft" ? "Draft" : "Live"} v${version.version}`,
                purpose: family.purpose,
            })),
    )
}

export function routeStatus(
    readiness: TwilioReadiness | undefined,
    purpose: TwilioMessagingPurpose,
): { ready: boolean; text: string } | null {
    if (!readiness) return null
    const gates = readiness.gates.filter((gate) => gate.route === purpose)
    if (gates.length === 0) return { ready: false, text: "not set up" }
    const blocking = gates.find((gate) => gate.status !== "pass")
    if (!blocking) return { ready: true, text: "ready" }
    return { ready: false, text: blocking.status === "pending" ? `${blocking.label} check required` : `${blocking.label} not ready` }
}

