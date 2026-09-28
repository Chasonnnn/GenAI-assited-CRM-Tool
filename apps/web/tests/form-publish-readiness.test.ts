import { describe, expect, it } from "vitest"

import { DEFAULT_FORM_DONOR_FIELD_OPTIONS } from "@/lib/api/forms"
import type { BuilderFormField, BuilderFormPage } from "@/lib/forms/form-builder-document"
import {
    getPublishReadinessItems,
    getPublishReadinessReason,
} from "@/lib/forms/form-publish-readiness"

function field(overrides: Partial<BuilderFormField>): BuilderFormField {
    return {
        id: "field",
        label: "Field",
        type: "text",
        required: false,
        helperText: "",
        surrogateFieldMapping: "",
        ...overrides,
    }
}

function pagesWith(...fields: BuilderFormField[]): BuilderFormPage[] {
    return [{ id: 1, name: "Page 1", fields }]
}

describe("getPublishReadinessItems", () => {
    it("lists every critical identity mapping with a preset to add", () => {
        const items = getPublishReadinessItems({
            pages: pagesWith(field({ id: "name", surrogateFieldMapping: "full_name" })),
            leadKind: "surrogate",
            purpose: "surrogate_application",
            mappingOptions: [],
        })

        expect(items.map((item) => [item.label, item.status])).toEqual([
            ["Full Name", "ready"],
            ["Date of Birth", "missing"],
            ["Phone", "missing"],
            ["Email", "missing"],
        ])
        expect(items[1].addField?.surrogateFieldMapping).toBe("date_of_birth")
        expect(items[0].addField).toBeNull()
        expect(getPublishReadinessReason(items)).toBe(
            "To publish, add Date of Birth, Phone, Email.",
        )
    })

    it("accepts phone in place of email for lead capture forms", () => {
        const items = getPublishReadinessItems({
            pages: pagesWith(
                field({ id: "name", surrogateFieldMapping: "full_name" }),
                field({ id: "phone", type: "phone", surrogateFieldMapping: "phone" }),
            ),
            leadKind: "surrogate",
            purpose: "lead_capture",
            mappingOptions: [],
        })

        expect(items.every((item) => item.status === "ready")).toBe(true)
        expect(getPublishReadinessReason(items)).toBeNull()
    })

    it("flags donor fields that are optional or the wrong type", () => {
        const items = getPublishReadinessItems({
            pages: pagesWith(
                field({ id: "name", required: true, surrogateFieldMapping: "full_name" }),
                field({ id: "email", type: "email", required: false, surrogateFieldMapping: "email" }),
                field({ id: "photo", type: "text", required: true, surrogateFieldMapping: "profile_photo" }),
            ),
            leadKind: "egg_donor",
            purpose: "lead_capture",
            mappingOptions: DEFAULT_FORM_DONOR_FIELD_OPTIONS,
        })

        expect(items.map((item) => [item.key, item.status, item.fieldId])).toEqual([
            ["full_name", "ready", "name"],
            ["email", "not_required", "email"],
            ["profile_photo", "wrong_type", "photo"],
        ])
        expect(getPublishReadinessReason(items)).toBe(
            "To publish, mark Email required; change the field type for Profile Photo.",
        )
    })
})
