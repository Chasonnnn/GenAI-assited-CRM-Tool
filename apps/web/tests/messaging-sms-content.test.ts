import { describe, expect, it } from "vitest"

import type { MessagingTemplateVersion } from "@/lib/api/twilio"
import {
    countSmsSegments,
    groupTemplateFamilies,
    optInRequirements,
    renderSmsBody,
} from "@/lib/messaging/sms-content"
import { routeStatus, testTemplateOptions, usageSummary } from "@/lib/messaging/template-library"

function version(overrides: Partial<MessagingTemplateVersion>): MessagingTemplateVersion {
    return {
        id: "v1",
        template_key: "family-1",
        version: 1,
        name: "Reminder",
        purpose: "operational",
        body: "Hi",
        status: "draft",
        is_enrollment_confirmation: false,
        content_classification: "no_phi",
        published_at: null,
        created_at: "2026-10-01T12:00:00Z",
        ...overrides,
    }
}

describe("countSmsSegments", () => {
    it("counts GSM-7 text in 160 and 153 character segments", () => {
        expect(countSmsSegments("")).toEqual({ characters: 0, segments: 0 })
        expect(countSmsSegments("a".repeat(160))).toEqual({ characters: 160, segments: 1 })
        expect(countSmsSegments("a".repeat(161))).toEqual({ characters: 161, segments: 2 })
    })

    it("counts extended GSM characters twice and switches to UCS-2 for other characters", () => {
        expect(countSmsSegments("€".repeat(80)).segments).toBe(1)
        expect(countSmsSegments("€".repeat(81)).segments).toBe(2)
        expect(countSmsSegments("’".repeat(70)).segments).toBe(1)
        expect(countSmsSegments("’".repeat(71)).segments).toBe(2)
    })
})

describe("optInRequirements", () => {
    const settings = {
        legal_messaging_brand: "EWI Family Global",
        expected_frequency: "Msg frequency varies",
        support_contact: "(512) 555-0100",
    }

    it("passes the CTIA minimum with the brand, frequency, rates, help, and stop", () => {
        const body =
            "EWI Family Global: You're signed up for texts. Msg frequency varies. Msg & data rates may apply. Reply HELP for help, STOP to opt out."
        expect(optInRequirements(body, settings).every((requirement) => requirement.met)).toBe(true)
    })

    it("accepts own-words frequency and the support number in place of HELP", () => {
        const body = "EWI Family Global: up to 4 msgs/month. Message and data rates may apply. Call (512) 555-0100. Text STOP to end."
        expect(optInRequirements(body, settings).every((requirement) => requirement.met)).toBe(true)
    })

    it("lists each missing item", () => {
        const missing = optInRequirements("Welcome!", settings)
            .filter((requirement) => !requirement.met)
            .map((requirement) => requirement.label)
        expect(missing).toEqual([
            "Brand name",
            "Message frequency",
            "Message and data rates",
            "HELP or support contact",
            "STOP instructions",
        ])
    })
})

describe("template library helpers", () => {
    it("fills variables as plain text and blanks unknown ones", () => {
        expect(renderSmsBody("Hi {{ first_name }} {{nope}}& co", { first_name: "O'Brien" })).toBe("Hi O'Brien & co")
    })

    it("groups versions into families with their live and draft versions", () => {
        const [family] = groupTemplateFamilies([
            version({ id: "v1", version: 1, status: "retired" }),
            version({ id: "v2", version: 2, status: "published" }),
            version({ id: "v3", version: 3, status: "draft", name: "Reminder v3" }),
        ])
        expect(family?.name).toBe("Reminder v3")
        expect(family?.live?.id).toBe("v2")
        expect(family?.draft?.id).toBe("v3")
        expect(testTemplateOptions(family ? [family] : []).map((option) => option.label)).toEqual([
            "Reminder v3 · Draft v3",
            "Reminder v3 · Live v2",
        ])
    })

    it("summarizes usage and route status", () => {
        expect(usageSummary([])).toBeNull()
        expect(
            usageSummary([
                { kind: "workflow", id: "w1", name: "A" },
                { kind: "workflow", id: "w2", name: "B" },
                { kind: "campaign", id: "c1", name: "C" },
            ]),
        ).toBe("2 workflows · 1 campaign")
        const readiness = {
            gates: [
                { key: "operational_route", label: "Operational route", status: "pass", detail: null, route: "operational" },
                { key: "operational_sender_registration", label: "A2P campaign", status: "fail", detail: "Pending", route: "operational" },
            ],
        } as unknown as Parameters<typeof routeStatus>[0]
        expect(routeStatus(readiness, "operational")).toEqual({ ready: false, text: "A2P campaign not ready" })
        expect(routeStatus(readiness, "promotional")).toEqual({ ready: false, text: "not set up" })
    })
})
