import type { JsonObject } from "@/lib/types/json"

export const PROFILE_HEADER_NAME_KEY = "__profile_header_name"
export const PROFILE_HEADER_NOTE_KEY = "__profile_header_note"
export const PROFILE_CUSTOM_QAS_KEY = "__profile_custom_qas"

export function renderProfileTemplate(template: string, values: JsonObject): string {
    return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_match, token) => {
        const value = values[token]
        if (value === null || value === undefined) {
            return `{{${token}}}`
        }
        return String(value)
    })
}
