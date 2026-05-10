import { describe, expect, it } from "vitest"

import { buildFormSchema, buildMappings, createBuilderField, schemaToPages } from "@/lib/forms/form-builder-document"
import { PRESET_FIELD_GROUPS } from "@/lib/forms/form-builder-library"

const metadata = {
    publicTitle: "",
    logoUrl: "",
    privacyNotice: "",
}

describe("form builder journey timing preset", () => {
    it("serializes the journey timing preset with canonical option values", () => {
        const journeyTimingTemplate = PRESET_FIELD_GROUPS
            .flatMap((group) => group.fields)
            .find((field) => field.key === "journey_timing_preference")

        expect(journeyTimingTemplate).toBeTruthy()

        const schema = buildFormSchema(
            [
                {
                    id: 1,
                    name: "Page 1",
                    fields: [createBuilderField(journeyTimingTemplate!)],
                },
            ],
            metadata,
        )

        expect(schema.pages[0]?.fields[0]?.options).toEqual([
            { label: "0–3 months", value: "months_0_3" },
            { label: "3–6 months", value: "months_3_6" },
            { label: "Still deciding", value: "still_deciding" },
        ])
    })

    it("preserves journey timing label/value pairs when loading a schema back into the builder", () => {
        const pages = schemaToPages(
            {
                pages: [
                    {
                        fields: [
                            {
                                key: "journey_timing_preference",
                                label: "When would you like to start your surrogacy journey?",
                                type: "radio",
                                options: [
                                    { label: "0–3 months", value: "months_0_3" },
                                    { label: "3–6 months", value: "months_3_6" },
                                    { label: "Still deciding", value: "still_deciding" },
                                ],
                            },
                        ],
                    },
                ],
            },
            new Map(),
        )

        expect(pages[0]?.fields[0]?.options).toEqual([
            { label: "0–3 months", value: "months_0_3" },
            { label: "3–6 months", value: "months_3_6" },
            { label: "Still deciding", value: "still_deciding" },
        ])
    })
})

describe("form builder field mappings", () => {
    it("collects mapped fields in page and field order", () => {
        const mappings = buildMappings([
            {
                id: 1,
                name: "Page 1",
                fields: [
                    {
                        id: "full_name",
                        type: "text",
                        label: "Full name",
                        required: true,
                        surrogateFieldMapping: "full_name",
                    },
                    {
                        id: "notes",
                        type: "textarea",
                        label: "Notes",
                        required: false,
                    },
                ],
            },
            {
                id: 2,
                name: "Page 2",
                fields: [
                    {
                        id: "email",
                        type: "email",
                        label: "Email",
                        required: true,
                        surrogateFieldMapping: "email",
                    },
                ],
            },
        ])

        expect(mappings).toEqual([
            { field_key: "full_name", surrogate_field: "full_name" },
            { field_key: "email", surrogate_field: "email" },
        ])
    })
})
