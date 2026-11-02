import { describe, expect, it } from "vitest"

import config from "../vitest.config"

describe("Vitest per-file state", () => {
    it("shares workers between files only with the per-file reset running first", () => {
        expect(config.test?.isolate).toBe(false)
        expect(config.test?.setupFiles).toEqual(["./tests/reset-file-state.ts", "./tests/setup.ts"])
    })

    it("starts each file with empty browser storage and an empty document", () => {
        // Earlier files in this worker may have written storage and rendered into the body.
        expect(window.localStorage.length).toBe(0)
        expect(window.sessionStorage.length).toBe(0)
        expect(document.body.childElementCount).toBe(0)
    })
})
