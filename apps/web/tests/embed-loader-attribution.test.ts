import { afterEach, describe, expect, it, vi } from "vitest"

import { GET } from "../app/embed/forms.v1.js/route"

type InitMessage = { type: string; attribution: Record<string, string> }

const originalLocation = window.location

function setLocation(url: string) {
    const next = new URL(url, "https://www.ewisurrogacy.com")
    Object.defineProperty(window, "location", {
        writable: true,
        value: { ...originalLocation, href: next.href, origin: next.origin, search: next.search },
    })
}

async function mountLoaderAndReadAttribution(url: string): Promise<Record<string, string>> {
    setLocation(url)
    document.body.innerHTML = '<div data-sf-form="lead-form"></div>'
    const script = await GET().text()
    new Function(script)()

    const iframe = document.querySelector("iframe")
    if (!iframe) throw new Error("Loader did not mount an iframe")
    const postMessage = vi.fn()
    Object.defineProperty(iframe, "contentWindow", { configurable: true, value: { postMessage } })
    window.dispatchEvent(
        new MessageEvent("message", {
            origin: new URL(iframe.src).origin,
            data: { type: "sf:form:ready" },
        }),
    )
    const message = postMessage.mock.calls[0]?.[0] as InitMessage | undefined
    if (!message) throw new Error("Loader did not send sf:form:init")
    return message.attribution
}

describe("embed loader attribution", () => {
    afterEach(() => {
        vi.useRealTimers()
        document.body.innerHTML = ""
        Object.defineProperty(window, "location", { writable: true, value: originalLocation })
    })

    it("builds fbc from fbclid with a millisecond creation time", async () => {
        vi.useFakeTimers({ toFake: ["Date"] })
        vi.setSystemTime(new Date("2026-09-27T12:00:00.123Z"))

        const attribution = await mountLoaderAndReadAttribution("/apply?fbclid=click-123&utm_source=facebook")

        expect(attribution.fbc).toBe(`fb.1.${Date.parse("2026-09-27T12:00:00.123Z")}.click-123`)
        expect(attribution.fbclid).toBe("click-123")
        expect(attribution.utm_source).toBe("facebook")
    })

    it("keeps an explicit fbc query value over the fbclid fallback", async () => {
        const attribution = await mountLoaderAndReadAttribution(
            "/apply?fbclid=click-123&fbc=fb.1.1772942400000.click-123",
        )

        expect(attribution.fbc).toBe("fb.1.1772942400000.click-123")
    })
})
