import { describe, expect, it } from "vitest"

import {
    buildFormSchema,
    buildMappings,
    createBuilderField,
    schemaToMetadata,
    schemaToPages,
} from "@/lib/forms/form-builder-document"
import { PRESET_FIELD_GROUPS } from "@/lib/forms/form-builder-library"

const metadata = {
    publicEyebrow: "",
    publicTitle: "",
    publicSubtitle: "",
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

describe("form builder mapped field defaults", () => {
    it("applies canonical public validation when surrogate fields are reused with custom field keys", () => {
        const schema = buildFormSchema(
            [
                {
                    id: 1,
                    name: "Applicant details",
                    fields: [
                        {
                            id: "current_state",
                            type: "text",
                            label: "State",
                            helperText: "",
                            required: true,
                            surrogateFieldMapping: "state",
                        },
                        {
                            id: "current_height",
                            type: "number",
                            label: "Height",
                            helperText: "",
                            required: true,
                            surrogateFieldMapping: "height_ft",
                        },
                        {
                            id: "current_weight",
                            type: "number",
                            label: "Weight",
                            helperText: "",
                            required: true,
                            surrogateFieldMapping: "weight_lb",
                        },
                        {
                            id: "delivery_count",
                            type: "number",
                            label: "Deliveries",
                            helperText: "",
                            required: true,
                            surrogateFieldMapping: "num_deliveries",
                        },
                        {
                            id: "csection_count",
                            type: "number",
                            label: "C-sections",
                            helperText: "",
                            required: true,
                            surrogateFieldMapping: "num_csections",
                        },
                    ],
                },
            ],
            metadata,
        )

        const fields = schema.pages[0]?.fields ?? []

        expect(fields.find((field) => field.key === "current_state")).toMatchObject({
            type: "text",
            help_text: "Use the 2-letter state code, e.g. CA.",
            validation: {
                min_length: 2,
                max_length: 2,
                pattern: "^[A-Za-z]{2}$",
            },
        })
        expect(fields.find((field) => field.key === "current_height")).toMatchObject({
            type: "height",
        })
        expect(fields.find((field) => field.key === "current_weight")).toMatchObject({
            type: "number",
            validation: { min_value: 1, max_value: 1000 },
        })
        expect(fields.find((field) => field.key === "delivery_count")).toMatchObject({
            type: "number",
            validation: { min_value: 1, max_value: 20 },
        })
        expect(fields.find((field) => field.key === "csection_count")).toMatchObject({
            type: "number",
            validation: { min_value: 0, max_value: 20 },
        })
    })
})

describe("form builder public header metadata", () => {
    it("preserves intentionally empty public header fields", () => {
        const schema = buildFormSchema(
            [
                {
                    id: 1,
                    name: "Eligibility",
                    fields: [],
                },
            ],
            metadata,
        )

        expect(schema.public_eyebrow).toBe("")
        expect(schema.public_title).toBe("")
        expect(schema.public_subtitle).toBe("")
    })

    it("does not backfill blank public header metadata from page title", () => {
        const metadataFromSchema = schemaToMetadata({
            pages: [
                {
                    title: "Eligibility",
                    fields: [],
                },
            ],
        })

        expect(metadataFromSchema.publicEyebrow).toBe("")
        expect(metadataFromSchema.publicTitle).toBe("")
        expect(metadataFromSchema.publicSubtitle).toBe("")
    })
})
