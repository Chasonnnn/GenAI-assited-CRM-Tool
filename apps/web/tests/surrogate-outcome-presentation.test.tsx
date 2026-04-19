import { describe, expect, it } from "vitest"

import {
    getContactOutcomePresentation,
    getInterviewOutcomePresentation,
} from "@/lib/surrogate-outcome-presentation"

describe("surrogate outcome presentation", () => {
    it("maps contact outcomes to friendly labels and tones", () => {
        expect(getContactOutcomePresentation("reached")).toMatchObject({
            label: "Reached",
            tone: "success",
        })
        expect(getContactOutcomePresentation("no_answer")).toMatchObject({
            label: "No Answer",
            tone: "follow_up",
        })
        expect(getContactOutcomePresentation("voicemail")).toMatchObject({
            label: "Voicemail",
            tone: "follow_up",
        })
        expect(getContactOutcomePresentation("wrong_number")).toMatchObject({
            label: "Wrong Number",
            tone: "failed",
        })
        expect(getContactOutcomePresentation("email_bounced")).toMatchObject({
            label: "Email Bounced",
            tone: "failed",
        })
    })

    it("maps interview outcomes to friendly labels and tones", () => {
        expect(getInterviewOutcomePresentation("completed")).toMatchObject({
            label: "Completed",
            tone: "success",
        })
        expect(getInterviewOutcomePresentation("rescheduled")).toMatchObject({
            label: "Rescheduled",
            tone: "follow_up",
        })
        expect(getInterviewOutcomePresentation("no_show")).toMatchObject({
            label: "No Show",
            tone: "failed",
        })
        expect(getInterviewOutcomePresentation("cancelled")).toMatchObject({
            label: "Cancelled",
            tone: "neutral",
        })
    })
})
