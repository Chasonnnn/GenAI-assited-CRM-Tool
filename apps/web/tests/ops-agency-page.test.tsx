import { describe, it, expect, vi } from "vitest"

const dynamicState = vi.hoisted(() => ({
    calls: [] as Array<{ options?: { ssr?: boolean } }>,
}))

vi.mock("next/dynamic", () => ({
    __esModule: true,
    default: (_loader: unknown, options: { ssr?: boolean } = {}) => {
        dynamicState.calls.push({ options })
        return () => null
    },
}))

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: () => null,
}))

import "../app/ops/agencies/[orgId]/page"

describe("OpsAgencyPage", () => {
    it("lazy loads the rich text editor", () => {
        expect(dynamicState.calls.length).toBeGreaterThan(0)
        expect(dynamicState.calls.some((call) => call.options?.ssr === false)).toBe(true)
    })
})
