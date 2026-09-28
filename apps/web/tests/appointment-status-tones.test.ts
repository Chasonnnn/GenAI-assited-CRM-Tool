import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

import { APPOINTMENT_STATUSES, getAppointmentStatusTone } from "@/lib/appointment-status-tones"

type Rgb = [number, number, number]

const paletteCss = readFileSync(path.join(process.cwd(), "node_modules/tailwindcss/theme.css"), "utf8")

function paletteColor(name: string): Rgb {
    const match = paletteCss.match(new RegExp(`--color-${name}: oklch\\(([\\d.]+)% ([\\d.]+) ([\\d.]+)\\)`))
    if (!match) throw new Error(`Missing Tailwind color ${name}`)
    return oklchToSrgb(Number(match[1]) / 100, Number(match[2]), Number(match[3]))
}

function oklchToSrgb(lightness: number, chroma: number, hue: number): Rgb {
    const a = chroma * Math.cos((hue * Math.PI) / 180)
    const b = chroma * Math.sin((hue * Math.PI) / 180)
    const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
    const linear = [
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ]
    return linear.map((value) => {
        const clipped = Math.min(Math.max(value, 0), 1)
        return clipped <= 0.0031308 ? 12.92 * clipped : 1.055 * clipped ** (1 / 2.4) - 0.055
    }) as Rgb
}

function composite(foreground: Rgb, background: Rgb, alpha: number): Rgb {
    return foreground.map((value, index) => alpha * value + (1 - alpha) * background[index]!) as Rgb
}

function luminance(color: Rgb): number {
    const [r, g, b] = color.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}

function contrastRatio(first: Rgb, second: Rgb): number {
    const [high, low] = [luminance(first), luminance(second)].toSorted((x, y) => y - x)
    return (high! + 0.05) / (low! + 0.05)
}

// --card and --background from app/globals.css (:root and .dark).
const SURFACES = {
    light: [oklchToSrgb(1, 0, 0), oklchToSrgb(0.985, 0, 0)],
    dark: [oklchToSrgb(0.218, 0, 0), oklchToSrgb(0.182, 0, 0)],
}

function tintParts(tint: string) {
    const background = tint.match(/(?:^| )bg-([a-z]+-\d+)\/(\d+)/)
    const lightText = tint.match(/(?:^| )text-([a-z]+-\d+)/)
    const darkText = tint.match(/dark:text-([a-z]+-\d+)/)
    if (!background || !lightText || !darkText) throw new Error(`Unexpected tint: ${tint}`)
    return {
        background: paletteColor(background[1]!),
        alpha: Number(background[2]) / 100,
        lightText: paletteColor(lightText[1]!),
        darkText: paletteColor(darkText[1]!),
    }
}

describe("appointment status tones", () => {
    it.each(APPOINTMENT_STATUSES)("keeps %s chip text at 4.5:1 or more in light and dark", (status) => {
        const { tint } = getAppointmentStatusTone(status)
        const parts = tintParts(tint)
        for (const surface of SURFACES.light) {
            expect(contrastRatio(parts.lightText, composite(parts.background, surface, parts.alpha))).toBeGreaterThanOrEqual(4.5)
        }
        for (const surface of SURFACES.dark) {
            expect(contrastRatio(parts.darkText, composite(parts.background, surface, parts.alpha))).toBeGreaterThanOrEqual(4.5)
        }
    })

    it("never pairs a status tint with white text", () => {
        for (const status of APPOINTMENT_STATUSES) {
            expect(getAppointmentStatusTone(status).tint).not.toMatch(/text-white/)
        }
    })

    it("maps unknown statuses to the neutral tone", () => {
        expect(getAppointmentStatusTone("rescheduled")).toEqual(getAppointmentStatusTone("expired"))
        expect(getAppointmentStatusTone("toString")).toEqual(getAppointmentStatusTone("expired"))
    })
})
