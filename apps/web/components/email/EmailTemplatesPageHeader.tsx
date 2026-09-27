import type { ReactNode } from "react"
import { PlusIcon, SparklesIcon } from "lucide-react"

import Link from "@/components/app-link"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"

export function EmailTemplatesPageHeader({
    activeTab,
    canUseAI,
    canManageEmailTemplates,
    onCreatePersonal,
    onCreateOrganization,
}: {
    activeTab: string
    canUseAI: boolean
    canManageEmailTemplates: boolean
    onCreatePersonal: () => void
    onCreateOrganization: () => void
}) {
    let actions: ReactNode = null
    if (activeTab === "personal") {
        actions = (
            <>
                {canUseAI ? (
                    <Button variant="outline" title="Generate email template with AI" render={<Link href="/automation/ai-builder?mode=email_template" />}><SparklesIcon className="mr-2 size-4" />Generate with AI</Button>
                ) : (
                    <Button variant="outline" disabled title="AI is disabled or permission is missing"><SparklesIcon className="mr-2 size-4" />Generate with AI</Button>
                )}
                <Button onClick={onCreatePersonal}><PlusIcon className="mr-2 size-4" />Create Template</Button>
            </>
        )
    } else if (activeTab === "org" && canManageEmailTemplates) {
        actions = <Button onClick={onCreateOrganization}><PlusIcon className="mr-2 size-4" />Create Org Template</Button>
    }

    return <PageHeader title="Email Templates" actions={actions} />
}
