import type {
    FieldType,
    FormFieldColumn,
    FormFieldOption,
    FormFieldRow,
    FormFieldValidation,
    FormSchema,
} from "@/lib/api/forms"
import type { BuilderOption, BuilderPaletteField } from "@/lib/forms/form-builder-library"

export type BuilderFormField = {
    id: string
    type: FieldType
    label: string
    helperText: string
    required: boolean
    surrogateFieldMapping: string
    options?: BuilderOption[]
    validation?: FormFieldValidation | null
    showIf?: {
        fieldKey: string
        operator: "equals" | "not_equals" | "contains" | "not_contains" | "is_empty" | "is_not_empty"
        value?: string
    } | null
    columns?: {
        id: string
        label: string
        type: FormFieldColumn["type"]
        required: boolean
        options?: string[]
        validation?: FormFieldValidation | null
    }[]
    rows?: {
        id: string
        label: string
        helpText: string
    }[]
    minRows?: number | null
    maxRows?: number | null
}

export type BuilderShowIfOperator = NonNullable<BuilderFormField["showIf"]>["operator"]

export type BuilderFormPage = {
    id: number
    name: string
    fields: BuilderFormField[]
}

export type BuilderSchemaMetadata = {
    publicTitle: string
    logoUrl: string
    privacyNotice: string
}

export const FALLBACK_FORM_PAGE: BuilderFormPage = { id: 1, name: "Page 1", fields: [] }

export function getBuilderOptionLabel(option: BuilderOption) {
    return typeof option === "string" ? option : option.label
}

export function getBuilderOptionValue(option: BuilderOption) {
    return typeof option === "string" ? option : option.value
}

export function updateBuilderOptionLabel(option: BuilderOption, label: string): BuilderOption {
    return typeof option === "string" ? label : { ...option, label }
}

const toBuilderOptions = (options?: FormFieldOption[] | null): BuilderOption[] | undefined => {
    if (!options || options.length === 0) return undefined
    return options.map((option) =>
        option.label === option.value
            ? option.label
            : {
                label: option.label,
                value: option.value,
            },
    )
}

const toFieldOptions = (options?: BuilderOption[]): FormFieldOption[] | null => {
    if (!options || options.length === 0) return null
    return options.map((option) => ({
        label: getBuilderOptionLabel(option),
        value: getBuilderOptionValue(option),
    }))
}

const toFieldRows = (
    rows?: BuilderFormField["rows"],
): FormFieldRow[] | null => {
    if (!rows || rows.length === 0) return null
    return rows.map((row) => ({
        key: row.id,
        label: row.label,
        help_text: row.helpText || null,
    }))
}

export function buildFormSchema(pages: BuilderFormPage[], metadata: BuilderSchemaMetadata): FormSchema {
    const publicTitle = metadata.publicTitle.trim()
    const logoUrl = metadata.logoUrl.trim()
    const privacyNotice = metadata.privacyNotice.trim()

    return {
        pages: pages.map((page) => ({
            title: page.name || null,
            fields: page.fields.map((field) => ({
                key: field.id,
                label: field.label,
                type: field.type,
                required: field.required,
                options: toFieldOptions(field.options),
                validation: field.validation ?? null,
                help_text: field.helperText || null,
                show_if: field.showIf
                    ? {
                        field_key: field.showIf.fieldKey,
                        operator: field.showIf.operator,
                        value: field.showIf.value ?? null,
                    }
                    : null,
                columns: field.columns
                    ? field.columns.map((column) => ({
                        key: column.id,
                        label: column.label,
                        type: column.type,
                        required: column.required,
                        options: toFieldOptions(column.options),
                        validation: column.validation ?? null,
                    }))
                    : null,
                rows: toFieldRows(field.rows),
                min_rows: field.minRows ?? null,
                max_rows: field.maxRows ?? null,
            })),
        })),
        public_title: publicTitle || null,
        logo_url: logoUrl || null,
        privacy_notice: privacyNotice || null,
    }
}

export function schemaToPages(schema: FormSchema, mappings: Map<string, string>): BuilderFormPage[] {
    const pages = schema.pages.map((page, index) => ({
        id: index + 1,
        name: page.title || `Page ${index + 1}`,
        fields: page.fields.map((field) => {
            const options = toBuilderOptions(field.options)
            const columns = field.columns?.map((column) => {
                const columnOptions = column.options?.map((option) => option.label || option.value)
                return {
                    id: column.key,
                    label: column.label,
                    type: column.type,
                    required: column.required ?? false,
                    ...(columnOptions ? { options: columnOptions } : {}),
                    validation: column.validation ?? null,
                }
            })
            const showIf =
                field.show_if
                    ? {
                        fieldKey: field.show_if.field_key,
                        operator: field.show_if.operator,
                        ...(field.show_if.value !== null && field.show_if.value !== undefined
                            ? { value: String(field.show_if.value) }
                            : {}),
                    }
                    : null
            const rows = field.rows?.map((row) => ({
                id: row.key,
                label: row.label,
                helpText: row.help_text || "",
            }))
            return {
                id: field.key,
                type: field.type,
                label: field.label,
                helperText: field.help_text || "",
                required: field.required ?? false,
                surrogateFieldMapping: mappings.get(field.key) || "",
                validation: field.validation ?? null,
                showIf,
                ...(columns && columns.length > 0 ? { columns } : {}),
                ...(rows && rows.length > 0 ? { rows } : {}),
                minRows: field.min_rows ?? null,
                maxRows: field.max_rows ?? null,
                ...(options ? { options } : {}),
            }
        }),
    }))

    return pages.length > 0 ? pages : [FALLBACK_FORM_PAGE]
}

export function schemaToMetadata(schema?: FormSchema | null): BuilderSchemaMetadata {
    return {
        publicTitle: schema?.public_title ?? "",
        logoUrl: schema?.logo_url ?? "",
        privacyNotice: schema?.privacy_notice ?? "",
    }
}

export function buildMappings(pages: BuilderFormPage[]): { field_key: string; surrogate_field: string }[] {
    return pages.flatMap((page) =>
        page.fields
            .filter((field) => field.surrogateFieldMapping)
            .map((field) => ({
                field_key: field.id,
                surrogate_field: field.surrogateFieldMapping,
            })),
    )
}

export const buildFieldId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `field-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export const buildColumnId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `col-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const buildRowId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `row-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function createBuilderField(template: BuilderPaletteField): BuilderFormField {
    const fieldId = buildFieldId()
    const baseField: BuilderFormField = {
        id: fieldId,
        type: template.type,
        label: template.label,
        helperText: template.helperText ?? "",
        required: template.required ?? false,
        surrogateFieldMapping: template.surrogateFieldMapping ?? "",
    }

    if (template.options && template.options.length > 0) {
        return {
            ...baseField,
            options: template.options.map((option) => (typeof option === "string" ? option : { ...option })),
        }
    }

    if (["select", "multiselect", "radio"].includes(template.type)) {
        return { ...baseField, options: ["Option 1", "Option 2", "Option 3"] }
    }

    if (template.type === "repeatable_table") {
        return {
            ...baseField,
            label: "Repeating Table",
            columns: [
                {
                    id: buildColumnId(),
                    label: "Column 1",
                    type: "text",
                    required: false,
                },
                {
                    id: buildColumnId(),
                    label: "Column 2",
                    type: "text",
                    required: false,
                },
            ],
            minRows: 0,
            maxRows: null,
        }
    }

    if (template.type === "table") {
        return {
            ...baseField,
            columns: [
                {
                    id: buildColumnId(),
                    label: "Response",
                    type: "radio",
                    required: true,
                    options: ["No", "Yes"],
                },
                {
                    id: buildColumnId(),
                    label: "If yes, explain",
                    type: "textarea",
                    required: false,
                },
            ],
            rows: [
                { id: buildRowId(), label: "Item 1", helpText: "" },
                { id: buildRowId(), label: "Item 2", helpText: "" },
                { id: buildRowId(), label: "Item 3", helpText: "" },
            ],
        }
    }

    return baseField
}

export function normalizeValidation(
    current: FormFieldValidation | null | undefined,
    updates: Partial<FormFieldValidation>,
) {
    const next: FormFieldValidation = {
        min_length: current?.min_length ?? null,
        max_length: current?.max_length ?? null,
        min_value: current?.min_value ?? null,
        max_value: current?.max_value ?? null,
        pattern: current?.pattern ?? null,
        ...updates,
    }

    if (next.pattern !== null && typeof next.pattern === "string" && next.pattern.trim() === "") {
        next.pattern = null
    }

    return Object.values(next).some((value) => value !== null && value !== undefined) ? next : null
}

export function parseOptionalNumber(value: string) {
    if (!value.trim()) return null
    const parsed = Number(value)
    return Number.isNaN(parsed) ? null : parsed
}

export function parseOptionalInt(value: string) {
    if (!value.trim()) return null
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? null : parsed
}
