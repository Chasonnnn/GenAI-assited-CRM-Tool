import { describe, expect, it } from "vitest"

import robots from "../app/robots"

describe("robots metadata route", () => {
    it("allows public policy pages and blocks private app routes", () => {
        expect(robots()).toEqual({
            rules: {
                userAgent: "*",
                allow: ["/", "/privacy", "/privacy/", "/terms", "/terms/"],
                disallow: [
                    "/dashboard",
                    "/settings",
                    "/appointments",
                    "/surrogates",
                    "/intended-parents",
                    "/matches",
                    "/tasks",
                    "/reports",
                    "/automation",
                    "/ai-assistant",
                    "/ai-studio",
                    "/ops",
                    "/mfa",
                    "/auth",
                    "/invite",
                    "/book",
                    "/intake",
                    "/embed",
                    "/email/unsubscribe",
                ],
            },
        })
    })
})
