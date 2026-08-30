import type { Route } from "next"

import type { EmailTemplateListItem } from "@/lib/api/email-templates"

export function getTemplateStudioHref(template: EmailTemplateListItem): Route {
    return `/automation/email-templates/${template.scope}/${template.id}` as Route
}
