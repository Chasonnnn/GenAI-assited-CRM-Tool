import type { RecordModule, RecordScopeRule } from "@/lib/api/record-scopes"
import { MODULE_LABELS, scopeLabel } from "./permission-controls"

export function PermissionScopeChanges({ before, after }: { before: Record<RecordModule, RecordScopeRule>; after: Record<RecordModule, RecordScopeRule> }) {
    return <section className="space-y-3"><h3 className="text-sm font-semibold">Record scope changes</h3>{(Object.keys(MODULE_LABELS) as RecordModule[]).map((module) => <div key={module} className="rounded-xl border p-3 text-sm"><h4 className="mb-2 font-medium">{MODULE_LABELS[module]}</h4><div className="grid gap-2 sm:grid-cols-2"><div><span className="text-xs text-muted-foreground">Before</span><p>{before[module] ? scopeLabel(before[module]) : "No role access"}</p></div><div><span className="text-xs text-muted-foreground">After</span><p>{after[module] ? scopeLabel(after[module]) : "No role access"}</p></div></div></div>)}</section>
}
