export type TemplateVariableValueType = "text" | "url" | "html"

export interface TemplateVariableRead {
    name: string
    description: string
    category: string
    required: boolean
    value_type: TemplateVariableValueType
    html_safe: boolean
}

