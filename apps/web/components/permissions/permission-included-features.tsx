import type { IncludedFeatures } from "@/lib/api/permissions"

export function PermissionIncludedFeatures({ features }: { features: IncludedFeatures }) {
    return <section className="mt-7 border-t border-[#45253f]/10 pt-6 dark:border-border">
        <h4 className="mb-4 font-semibold">Included for everyone</h4>
        <dl className="space-y-5 text-sm">
            <div><div className="flex items-center justify-between gap-3"><dt>Personal workspace</dt><dd className="text-xs text-muted-foreground">{features.personal_workspace ? "Included" : "Not included"}</dd></div><dd className="mt-1 text-xs text-muted-foreground">Workflows · Templates · Campaigns</dd></div>
            <div><div className="flex items-center justify-between gap-3"><dt>AI Assistant</dt><dd className="text-xs text-muted-foreground">{features.ai_assistant ? "Enabled" : "Disabled"}</dd></div><dd className="mt-1 text-xs text-muted-foreground">Organization setting</dd></div>
        </dl>
    </section>
}
