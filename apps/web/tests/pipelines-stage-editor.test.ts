import { describe, expect, it } from "vitest"

import type { PipelineStage } from "@/lib/api/pipelines"
import { DEFAULT_STAGE_SEMANTICS_BY_KEY, STAGE_DEFS } from "@/lib/constants/stages.generated"
import {
    getBehaviorPreset,
    getBehaviorPresetLabel,
    getPipelineSelectLabel,
    getPresetOptions,
    moveStageInList,
    normalizeEditableStage,
    normalizeSelectValue,
} from "@/lib/pipelines/stage-editor"

function defaultStage(stageKey: string, overrides: Partial<PipelineStage> = {}) {
    const definition = STAGE_DEFS.find((stage) => stage.stageKey === stageKey)
    if (!definition) throw new Error(`Unknown stage ${stageKey}`)
    return normalizeEditableStage(
        {
            id: stageKey,
            stage_key: definition.stageKey,
            slug: definition.slug,
            label: definition.label,
            color: definition.color,
            order: definition.order,
            stage_type: definition.stageType,
            is_active: true,
            is_locked: false,
            semantics: DEFAULT_STAGE_SEMANTICS_BY_KEY[definition.stageKey],
            ...overrides,
        } as PipelineStage,
        "surrogate",
    )
}

describe("getPresetOptions", () => {
    it("lists the seeded preset of unlocked post-approval default stages", () => {
        const options = getPresetOptions(defaultStage("medical_clearance_passed"), "surrogate")

        expect(options).toEqual([
            { value: "matched", label: "Matched" },
            { value: "custom", label: "Custom" },
        ])
    })

    it("keeps the selectable list unchanged when the current preset is selectable", () => {
        expect(getPresetOptions(defaultStage("contacted"), "surrogate").map((option) => option.value)).toEqual([
            "intake",
            "contacted",
            "custom",
        ])
    })

    it("names the current preset of every unlocked default stage", () => {
        for (const definition of STAGE_DEFS) {
            const stage = defaultStage(definition.stageKey)
            const current = getBehaviorPreset(stage, "surrogate")
            const options = getPresetOptions(stage, "surrogate")
            const values = options.map((option) => option.value)
            expect(new Set(values).size, definition.stageKey).toBe(values.length)
            expect(values, definition.stageKey).toContain("custom")
            expect(values, definition.stageKey).toContain(current)

            // The Behavior preset trigger renders this label for the current value.
            const label = getPipelineSelectLabel(options, normalizeSelectValue(current), "Behavior preset")
            expect(label, definition.stageKey).toMatch(/\S/)
            expect(label, definition.stageKey).not.toBe("Unknown option")
            expect(label, definition.stageKey).toBe(getBehaviorPresetLabel(current, "surrogate"))
        }
    })
})

describe("moveStageInList", () => {
    it("moves one stage, keeps the others in order and renumbers", () => {
        const stages = ["new_unread", "contacted", "pre_qualified", "matched"].map((key) => defaultStage(key))
        const ids = (list: typeof stages) => list.map((stage) => stage.id)

        expect(ids(moveStageInList(stages, 1, 3))).toEqual(["new_unread", "pre_qualified", "matched", "contacted"])
        expect(moveStageInList(stages, 3, 1).map((stage) => stage.order)).toEqual([1, 2, 3, 4])
        expect(moveStageInList(stages, 1, 1)).toBe(stages)
        expect(moveStageInList(stages, 1, 4)).toBe(stages)
    })
})
