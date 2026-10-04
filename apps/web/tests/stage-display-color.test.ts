import { describe, expect, it } from "vitest"

import { STAGE_DEFS } from "@/lib/constants/stages.generated"
import { CUSTOM_STAGE_COLOR_PRESETS } from "@/lib/pipeline-stage-colors"
import { stageDisplayColor } from "@/lib/stage-colors"

function contrastWithWhite(color: string) {
    const channels = [1, 3, 5].map((offset) => Number.parseInt(color.slice(offset, offset + 2), 16) / 255)
    const [r, g, b] = channels.map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)) as [
        number,
        number,
        number,
    ]
    return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)
}

function sweep() {
    const colors: string[] = []
    for (let r = 0; r <= 255; r += 51) {
        for (let g = 0; g <= 255; g += 51) {
            for (let b = 0; b <= 255; b += 51) {
                colors.push(`#${[r, g, b].map((value) => value.toString(16).padStart(2, "0")).join("")}`)
            }
        }
    }
    return colors
}

const SAMPLE_COLORS = [
    ...STAGE_DEFS.map((stage) => stage.color),
    ...Object.values(CUSTOM_STAGE_COLOR_PRESETS).flat(),
    "#FDE68A",
    "#fde68a",
    "#FFFFFF",
    ...sweep(),
]

describe("stageDisplayColor", () => {
    it("is idempotent, so saving the displayed color needs no migration", () => {
        for (const color of SAMPLE_COLORS) {
            const displayed = stageDisplayColor(color)
            expect(stageDisplayColor(displayed), color).toBe(displayed)
        }
    })

    it("reaches AA contrast with white text for every hex input", () => {
        for (const color of SAMPLE_COLORS) {
            expect(contrastWithWhite(stageDisplayColor(color)), color).toBeGreaterThanOrEqual(4.5)
        }
    })

    it("keeps colors that already reach AA and only normalizes their case", () => {
        expect(stageDisplayColor("#DB2777")).toBe("#DB2777")
        expect(stageDisplayColor("#0f766e")).toBe("#0F766E")
    })

    it("darkens light colors and leaves non-hex values unchanged", () => {
        expect(stageDisplayColor("#FDE68A")).not.toBe("#FDE68A")
        expect(stageDisplayColor("var(--primary)")).toBe("var(--primary)")
        expect(stageDisplayColor("")).toBe("")
    })

    it("stores picker presets as displayed colors", () => {
        for (const preset of Object.values(CUSTOM_STAGE_COLOR_PRESETS).flat()) {
            expect(stageDisplayColor(preset)).toBe(preset)
        }
    })
})
