"use client"

import { useState } from "react"
import Link from "@/components/app-link"
import { Check, ChevronRight, Lock, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useEffectivePermissions, useRoleDetail, useRoles, useUpdateRolePermissions } from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"
import { useRoleScopes } from "@/lib/hooks/use-record-scopes"
import type { RolePermission } from "@/lib/api/permissions"
import type { RecordModule, RecordScopeRule } from "@/lib/api/record-scopes"
import { cn } from "@/lib/utils"
import { MODULE_LABELS, PermissionError, PermissionLoading, ROLE_LABELS, ScopeFields, scopeLabel } from "./permission-controls"
import { PermissionAccessChecker } from "./permission-access-checker"
import { PermissionPolicyReview } from "./permission-policy-review"

const RECORD_MODULES: Record<string, RecordModule> = { Surrogates: "surrogates", Donors: "donors", "Intended Parents": "intended_parents" }

export function PermissionWorkspace({ initialRole = "case_manager" }: { initialRole?: string }) {
    const [role, setRole] = useState(initialRole)
    const [category, setCategory] = useState("Surrogates")
    const [tab, setTab] = useState("roles")
    const [changes, setChanges] = useState<Record<string, boolean>>({})
    const [scopeChanges, setScopeChanges] = useState<Partial<Record<RecordModule, RecordScopeRule>>>({})
    const [reviewOpen, setReviewOpen] = useState(false)
    const [pendingRole, setPendingRole] = useState<string | null>(null)
    const { user } = useAuth()
    const effective = useEffectivePermissions(user?.user_id ?? null)
    const canViewRoles = !!effective.data?.capabilities?.can_manage_roles || !!effective.data?.permissions?.includes("view_roles")
    const roles = useRoles(canViewRoles)
    const detail = useRoleDetail(canViewRoles ? role : null)
    const activePolicy = detail.data?.policy_version === 2
    const scopes = useRoleScopes(role, activePolicy)
    const save = useUpdateRolePermissions()
    const dirty = Object.keys(changes).length > 0 || Object.keys(scopeChanges).length > 0
    const editable = !!detail.data?.can_edit && !detail.data.protected
    const discard = () => { setChanges({}); setScopeChanges({}); save.reset() }
    const permissions: Record<string, RolePermission[]> = {}
    for (const [originalCategory, rows] of Object.entries(detail.data?.permissions_by_category ?? {})) {
        for (const row of rows) {
            if (activePolicy && row.key === "view_post_approval_surrogates") continue
            const group = ["manage_automation", "manage_org_workflows"].includes(row.key) ? "Workflows" : ["manage_email_templates", "manage_org_templates"].includes(row.key) ? "Templates" : originalCategory
            ;(permissions[group] ??= []).push(row)
        }
    }
    const currentCategory = permissions[category] ? category : Object.keys(permissions)[0] ?? "Surrogates"
    const currentRows = permissions[currentCategory] ?? []
    const module = RECORD_MODULES[currentCategory]
    const rule = module ? scopeChanges[module] ?? scopes.data?.[module] : undefined
    const allRows = Object.values(permissions).flat()
    const selectedActions = currentRows.filter((permission) => changes[permission.key] ?? permission.is_granted)
    const apply = async () => {
        try {
            await save.mutateAsync({ role, permissions: changes, ...(Object.keys(scopeChanges).length ? { scopeRules: scopeChanges } : {}) })
            discard()
            setReviewOpen(false)
        } catch { /* Mutation state keeps the review open with the server error. */ }
    }
    if (effective.isLoading) return <PermissionLoading />
    if (effective.error) return <div className="p-8"><PermissionError error={effective.error} retry={() => void effective.refetch()} /></div>
    if (!canViewRoles) return <div className="p-8"><h1 className="text-xl font-semibold">Permissions unavailable</h1></div>
    return <div className="flex min-h-full flex-1 flex-col bg-[#fcfafb] dark:bg-background">
        <div className="mx-auto w-full max-w-7xl px-5 py-7 sm:px-8 lg:px-10">
            <h1 className="text-3xl font-semibold tracking-tight text-[#45253f] dark:text-foreground">Permissions</h1>
            <nav aria-label="Permission settings" className="mt-7 flex gap-6 overflow-x-auto border-b text-sm">
                {[{ key: "roles", label: "Roles" }, ...(effective.data?.capabilities?.can_manage_members ? [{ key: "people", label: "People" }] : []), ...(effective.data?.capabilities?.can_manage_roles ? [{ key: "check", label: "Check access" }] : []), ...(!activePolicy && effective.data?.capabilities?.can_activate_policy ? [{ key: "upgrade", label: "Review upgrade" }] : [])].map((item) => item.key === "people" ?
                    <Link key={item.key} href="/settings/team" aria-disabled={dirty} onClick={(event) => { if (dirty) event.preventDefault() }} className={cn("shrink-0 pb-4", dirty && "pointer-events-none text-muted-foreground")}>{item.label}</Link> :
                    <Button key={item.key} variant="ghost" type="button" disabled={dirty && tab !== item.key} onClick={() => setTab(item.key)} aria-current={tab === item.key ? "page" : undefined} className={cn("h-auto shrink-0 rounded-none border-b-2 px-0 py-0 pb-4 font-medium hover:bg-transparent hover:text-primary disabled:opacity-40 dark:hover:bg-transparent", tab === item.key ? "border-primary text-primary" : "border-transparent text-muted-foreground")}>{item.label}</Button>)}
            </nav>
            {tab === "check" && <div className="py-8"><PermissionAccessChecker /></div>}
            {tab === "upgrade" && <div className="py-8"><PermissionPolicyReview /></div>}
            {tab === "roles" && <>
                {roles.isLoading ? <PermissionLoading /> : roles.error ? <div className="mt-6"><PermissionError error={roles.error} retry={() => void roles.refetch()} /></div> : !roles.data?.length ? <p className="py-8 text-muted-foreground">No roles available.</p> :
                    <div aria-label="Roles" className="my-7 flex gap-2 overflow-x-auto">{roles.data.map((item) => <Button key={item.role} variant="ghost" type="button" aria-pressed={role === item.role} onClick={() => { if (item.role === role) return; if (dirty) setPendingRole(item.role); else setRole(item.role) }} className={cn("flex h-auto min-h-12 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 py-3 text-sm font-medium transition-colors has-[>svg]:px-4", role === item.role ? "bg-[#45253f] text-white hover:bg-[#45253f] hover:text-white dark:bg-primary dark:hover:bg-primary" : "text-muted-foreground hover:bg-muted")}>
                        {ROLE_LABELS[item.role] || item.label}{item.protected && <Lock className="size-3.5" aria-label="Protected role" />}
                    </Button>)}</div>}
                {detail.isLoading ? <PermissionLoading /> : detail.error ? <PermissionError error={detail.error} retry={() => void detail.refetch()} /> : detail.data && <div className="grid gap-6 border-t pt-7 lg:grid-cols-[180px_1fr]">
                    <nav aria-label="Permission modules" className="flex gap-1 overflow-x-auto lg:flex-col">{Object.keys(permissions).map((item) => <Button key={item} variant="ghost" type="button" aria-current={currentCategory === item ? "page" : undefined} onClick={() => setCategory(item)} className={cn("flex h-auto items-center justify-between gap-3 whitespace-nowrap rounded-xl px-4 py-3 text-left text-sm font-normal has-[>svg]:px-4", currentCategory === item ? "bg-primary/10 font-semibold text-primary hover:bg-primary/10 hover:text-primary dark:hover:bg-primary/10" : "text-muted-foreground hover:bg-muted")}>
                        {item}{currentCategory === item && <ChevronRight className="size-4" aria-hidden="true" />}
                    </Button>)}</nav>
                    <div className="grid overflow-hidden rounded-2xl border bg-card shadow-sm xl:grid-cols-[minmax(0,1fr)_280px]">
                        <section className="min-w-0 p-6 sm:p-8">
                            <div className="mb-7 flex items-center justify-between gap-3"><div><h2 className="text-2xl font-semibold tracking-tight">{ROLE_LABELS[role] || detail.data.label}</h2><p className="mt-1 text-sm font-medium text-primary">{currentCategory}</p></div>{detail.data.protected && <span className="flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5 text-xs font-medium"><Lock className="size-3.5" />Protected</span>}</div>
                            {module && <section className="mb-8"><h3 className="mb-4 text-sm font-semibold">Record access</h3>
                                {!activePolicy ? <p className="rounded-xl bg-muted/60 p-4 text-sm text-muted-foreground">Record scope rules become available after the permission upgrade is reviewed and activated.</p> : scopes.isLoading ? <PermissionLoading /> : scopes.error ? <PermissionError error={scopes.error} retry={() => void scopes.refetch()} /> : rule ? <ScopeFields module={module} rule={rule} disabled={!editable || save.isPending} onChange={(next) => setScopeChanges((previous) => { const result = { ...previous }; if (JSON.stringify(next) === JSON.stringify(scopes.data?.[module])) delete result[module]; else result[module] = next; return result })} /> : <p className="text-sm text-muted-foreground">No scope rules available.</p>}
                            </section>}
                            <h3 className="mb-2 text-sm font-semibold">Actions</h3>
                            {currentRows.length === 0 && <p className="py-5 text-sm text-muted-foreground">No actions in this module.</p>}
                            <div className="divide-y">{currentRows.map((permission) => <label key={permission.key} className="flex min-h-14 items-center justify-between gap-5 py-3 text-sm">
                                <span>{permission.label}{permission.developer_only && <Lock className="ml-2 inline size-3 text-muted-foreground" aria-label="Developer only" />}</span>
                                <Switch checked={changes[permission.key] ?? permission.is_granted} disabled={!editable || permission.configurable === false || save.isPending} onCheckedChange={(granted) => setChanges((previous) => { const next = { ...previous }; if (granted === permission.is_granted) delete next[permission.key]; else next[permission.key] = granted; return next })} />
                            </label>)}</div>
                        </section>
                        <aside className="border-t bg-[#f8f0f6] p-6 dark:bg-muted/30 xl:border-l xl:border-t-0">
                            <h3 className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-primary" />Access preview</h3>
                            {rule && <p className="mt-5 text-sm font-medium leading-relaxed">{scopeLabel(rule)}</p>}
                            <p className="mb-3 mt-6 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Included actions</p>
                            {selectedActions.length ? <ul className="space-y-3 text-sm">{selectedActions.map((permission) => <li className="flex items-start gap-2" key={permission.key}><Check className="mt-0.5 size-4 shrink-0 text-primary" />{permission.label}</li>)}</ul> : <p className="text-sm text-muted-foreground">No actions enabled.</p>}
                            {module && <p className="mt-6 border-t pt-5 text-xs leading-relaxed text-muted-foreground">Individual additions and record collaborations can expand this role’s record scope.</p>}
                            {detail.data.protected && <p className="mt-6 border-t pt-5 text-sm text-muted-foreground">This role’s baseline cannot be changed.</p>}
                        </aside>
                    </div>
                </div>}
            </>}
        </div>
        {dirty && <div className="sticky bottom-0 z-20 mt-auto flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur-sm"><p className="text-sm font-medium">Unsaved changes</p><div className="flex gap-3"><Button variant="outline" disabled={save.isPending} onClick={discard}>Discard</Button><Button className="bg-[#45253f] text-white hover:bg-[#59334f] dark:bg-primary" disabled={save.isPending} onClick={() => setReviewOpen(true)}>Review changes</Button></div></div>}
        <Dialog open={reviewOpen} onOpenChange={(open) => { if (!save.isPending) setReviewOpen(open) }}><DialogContent><DialogHeader><DialogTitle>Review {ROLE_LABELS[role] || role} changes</DialogTitle></DialogHeader>
            <ul className="max-h-80 space-y-3 overflow-y-auto text-sm">{Object.entries(changes).map(([key, enabled]) => <li key={key} className="flex justify-between gap-4"><span>{allRows.find((row) => row.key === key)?.label ?? key}</span><span className={enabled ? "text-emerald-700" : "text-destructive"}>{enabled ? "Allow" : "Remove"}</span></li>)}{Object.entries(scopeChanges).map(([key, value]) => <li key={key}><span className="font-medium">{MODULE_LABELS[key as RecordModule]}</span><p className="mt-1 text-muted-foreground">{scopeLabel(value)}</p></li>)}</ul>
            {save.error && <PermissionError error={save.error} />}<DialogFooter><Button variant="outline" disabled={save.isPending} onClick={() => setReviewOpen(false)}>Back</Button><Button disabled={save.isPending} onClick={() => void apply()}>{save.isPending ? "Applying…" : "Apply changes"}</Button></DialogFooter>
        </DialogContent></Dialog>
        <Dialog open={pendingRole !== null} onOpenChange={(open) => { if (!open) setPendingRole(null) }}><DialogContent><DialogHeader><DialogTitle>Discard unsaved changes?</DialogTitle></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setPendingRole(null)}>Keep editing</Button><Button onClick={() => { discard(); setRole(pendingRole!); setPendingRole(null) }}>Discard changes</Button></DialogFooter></DialogContent></Dialog>
    </div>
}
