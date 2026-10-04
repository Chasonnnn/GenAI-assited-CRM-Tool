import { describe, expect, it } from "vitest"

import { buildSimpleCron, describeSchedule, parseSimpleCron } from "@/lib/workflows/workflow-editor-state"

describe("workflow schedule presets", () => {
    it.each([
        ["0 9 * * *", { frequency: "daily", time: "09:00", dayOfWeek: 1 }],
        ["30 7 * * 1-5", { frequency: "weekdays", time: "07:30", dayOfWeek: 1 }],
        ["15 18 * * 3", { frequency: "weekly", time: "18:15", dayOfWeek: 3 }],
        ["0 9 * * 7", { frequency: "weekly", time: "09:00", dayOfWeek: 0 }],
    ])("parses %s as a preset", (cron, schedule) => {
        expect(parseSimpleCron(cron)).toEqual(schedule)
    })

    it.each(["0 9 1 * *", "*/5 * * * *", "0 25 * * *", "0 9 * * 1,3"])("keeps %s as a custom cron", (cron) => {
        expect(parseSimpleCron(cron)?.frequency).toBe("custom")
    })

    it("treats an empty cron as unset", () => {
        expect(parseSimpleCron("  ")).toBeNull()
        expect(describeSchedule("")).toBeNull()
    })

    it("builds crons the scheduler accepts and round-trips them", () => {
        const weekly = { frequency: "weekly", time: "08:05", dayOfWeek: 5 } as const
        expect(buildSimpleCron(weekly)).toBe("5 8 * * 5")
        expect(parseSimpleCron(buildSimpleCron(weekly))).toEqual(weekly)
        expect(buildSimpleCron({ frequency: "weekdays", time: "17:00", dayOfWeek: 1 })).toBe("0 17 * * 1-5")
        expect(buildSimpleCron({ frequency: "daily", time: "", dayOfWeek: 1 })).toBe("0 0 * * *")
    })

    it("describes presets and falls back to the raw cron", () => {
        expect(describeSchedule("0 9 * * 1")).toBe("Every Monday at 09:00")
        expect(describeSchedule("0 9 * * 1-5")).toBe("Every weekday at 09:00")
        expect(describeSchedule("0 9 1 * *")).toBe("Cron 0 9 1 * *")
    })
})
