import { PlusIcon, SparklesIcon } from "lucide-react"

import Link from "@/components/app-link"
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
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <h1 className="text-2xl font-semibold">Email Templates</h1>
                <div className="flex items-center gap-2">
                    {activeTab === "personal" && (
                        <>
                            {canUseAI ? (
                                <Button variant="outline" title="Generate email template with AI" render={<Link href="/automation/ai-builder?mode=email_template" />}><SparklesIcon className="mr-2 size-4" />Generate with AI</Button>
                            ) : (
                                <Button variant="outline" disabled title="AI is disabled or permission is missing"><SparklesIcon className="mr-2 size-4" />Generate with AI</Button>
                            )}
                            <Button onClick={onCreatePersonal}><PlusIcon className="mr-2 size-4" />Create Template</Button>
                        </>
                    )}
                    {activeTab === "org" && canManageEmailTemplates && <Button onClick={onCreateOrganization}><PlusIcon className="mr-2 size-4" />Create Org Template</Button>}
                </div>
            </div>
        </div>
    )
}
