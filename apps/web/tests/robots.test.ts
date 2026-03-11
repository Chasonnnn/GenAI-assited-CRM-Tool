import { describe, expect, it } from "vitest"

import robots from "../app/robots"

describe("robots metadata route", () => {
    it("blocks crawlers from indexing the product app", () => {
        expect(robots()).toEqual({
            rules: {
                userAgent: "*",
                disallow: "/",
            },
        })
    })
})
