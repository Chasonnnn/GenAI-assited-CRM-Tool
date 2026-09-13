"use client"

import { useState } from "react"
import Link from "@/components/app-link"
import { Check, ChevronDown, Eye, Heart, Lock, Settings2, UsersRound, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useEffectivePermissions, useRoleDetail, useRoles, useUpdateRolePermissions } from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"
import { useRoleScopes } from "@/lib/hooks/use-record-scopes"
import type { PermissionTopic } from "@/lib/api/permissions"
import type { RecordModule, RecordScopeRule } from "@/lib/api/record-scopes"
import { cn } from "@/lib/utils"
import { MODULE_LABELS, PermissionError, PermissionLoading, ROLE_LABELS, ScopeFields, scopeLabel } from "./permission-controls"
import { PermissionAccessChecker } from "./permission-access-checker"
import { PermissionPolicyReview } from "./permission-policy-review"
import { groupRolePermissions, PERMISSION_TOPICS, permissionPreviewLabel } from "./permission-catalog"
import { PermissionIncludedFeatures } from "./permission-included-features"

const RECORD_MODULES: Partial<Record<PermissionTopic, RecordModule>> = { Surrogates: "surrogates", Donors: "donors", "Intended Parents": "intended_parents" }
const TOPIC_ICONS = { Surrogates: UsersRound, Donors: Heart, "Intended Parents": UsersRound, Operations: Zap, Administration: Settings2 }

export function PermissionWorkspace({ initialRole = "case_manager" }: { initialRole?: string }) {
    const [role, setRole] = useState(initialRole)
    const [topic, setTopic] = useState<PermissionTopic>("Surrogates")
    const [operation, setOperation] = useState("")
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
    const permissions = groupRolePermissions(detail.data)
    const operationSections = Object.keys(permissions.Operations)
    const currentOperation = operationSections.includes(operation) ? operation : operationSections[0]
    const sections = topic === "Operations" && currentOperation ? { [currentOperation]: permissions.Operations[currentOperation]! } : permissions[topic]
    const currentRows = Object.values(sections).flat()
    const module = RECORD_MODULES[topic]
    const rule = module ? scopeChanges[module] ?? scopes.data?.[module] : undefined
    const allRows = Object.values(permissions).flatMap((groups) => Object.values(groups).flat())
    const selectedActions = currentRows.filter((permission) => changes[permission.key] ?? permission.is_granted)
    const apply = async () => {
        if (!editable) return
        const editableChanges = Object.fromEntries(Object.entries(changes).filter(([key]) => allRows.some((row) => row.key === key && row.configurable !== false)))
        try {
            await save.mutateAsync({ role, permissions: editableChanges, ...(Object.keys(scopeChanges).length ? { scopeRules: scopeChanges } : {}) })
            discard()
            setReviewOpen(false)
        } catch { /* Mutation state keeps the review open with the server error. */ }
    }
    if (effective.isLoading) return <PermissionLoading />
    if (effective.error) return <div className="p-8"><PermissionError error={effective.error} retry={() => void effective.refetch()} /></div>
    if (!canViewRoles) return <div className="p-8"><h1 className="text-xl font-semibold">Permissions unavailable</h1></div>
    return <div className="flex min-h-full flex-1 flex-col bg-[#fdfbfc] text-[#352130] dark:bg-background dark:text-foreground">
        <div className="mx-auto w-full max-w-[1440px] px-5 py-7 sm:px-8 lg:px-10">
            <header className="flex flex-wrap items-center justify-between gap-x-8 gap-y-5">
                <h1 className="text-3xl font-semibold tracking-tight text-[#45253f] dark:text-foreground">Permissions</h1>
                <nav aria-label="Permission settings" className="flex max-w-full gap-6 overflow-x-auto text-sm">
                    {[{ key: "roles", label: "Roles" }, ...(effective.data?.capabilities?.can_manage_members ? [{ key: "people", label: "People" }] : []), ...(effective.data?.capabilities?.can_manage_roles ? [{ key: "check", label: "Check access" }] : []), ...(!activePolicy && effective.data?.capabilities?.can_activate_policy ? [{ key: "upgrade", label: "Review upgrade" }] : [])].map((item) => item.key === "people" ?
                        <Link key={item.key} href="/settings/team" aria-disabled={dirty} onClick={(event) => { if (dirty) event.preventDefault() }} className={cn("shrink-0 py-3", dirty && "pointer-events-none text-muted-foreground")}>{item.label}</Link> :
                        <Button key={item.key} variant="ghost" type="button" disabled={dirty && tab !== item.key} onClick={() => setTab(item.key)} aria-current={tab === item.key ? "page" : undefined} className={cn("h-auto shrink-0 rounded-none border-b-2 px-0 py-3 font-medium hover:bg-transparent hover:text-primary disabled:opacity-40 dark:hover:bg-transparent", tab === item.key ? "border-primary text-primary" : "border-transparent text-muted-foreground")}>{item.label}</Button>)}
                </nav>
            </header>
            {tab === "check" && <div className="py-8"><PermissionAccessChecker /></div>}
            {tab === "upgrade" && <div className="py-8"><PermissionPolicyReview /></div>}
            {tab === "roles" && <>
                {roles.isLoading ? <PermissionLoading /> : roles.error ? <div className="mt-6"><PermissionError error={roles.error} retry={() => void roles.refetch()} /></div> : !roles.data?.length ? <p className="py-8 text-muted-foreground">No roles available.</p> :
                    <div aria-label="Roles" className="my-7 flex gap-3 overflow-x-auto pb-1">{roles.data.map((item) => <Button key={item.role} variant="ghost" type="button" aria-label={ROLE_LABELS[item.role] || item.label} aria-pressed={role === item.role} onClick={() => { if (item.role === role) return; if (dirty) setPendingRole(item.role); else setRole(item.role) }} className={cn("flex h-auto min-h-12 flex-1 items-center justify-center gap-3 whitespace-nowrap rounded-xl border px-5 py-3 text-sm font-medium transition-colors has-[>svg]:px-5", role === item.role ? "border-[#45253f] bg-[#45253f] text-white hover:bg-[#45253f] hover:text-white dark:border-primary dark:bg-primary dark:hover:bg-primary" : "border-border bg-card hover:bg-muted")}>
                        {ROLE_LABELS[item.role] || item.label}{item.protected && <Lock className="size-4" aria-label="Protected role" />}
                    </Button>)}</div>}
                {detail.isLoading ? <PermissionLoading /> : detail.error ? <PermissionError error={detail.error} retry={() => void detail.refetch()} /> : detail.data && <div className="grid gap-6 border-t pt-6 lg:grid-cols-[180px_minmax(0,1fr)] xl:grid-cols-[210px_minmax(0,1fr)]">
                    <nav aria-label="Permission modules" className="flex flex-wrap content-start gap-1 lg:flex-col lg:border-r lg:pr-4">{PERMISSION_TOPICS.map((item) => {
                        const Icon = TOPIC_ICONS[item]
                        return <div key={item}>
                            <Button variant="ghost" type="button" aria-expanded={item === "Operations" ? topic === "Operations" : undefined} aria-current={topic === item ? "page" : undefined} onClick={() => setTopic(item)} className={cn("flex h-auto w-full items-center justify-start gap-3 whitespace-nowrap rounded-xl px-3 py-4 text-left text-sm font-normal has-[>svg]:px-3", topic === item ? "bg-primary/10 font-semibold text-primary hover:bg-primary/10 hover:text-primary dark:hover:bg-primary/10" : "hover:bg-muted")}><Icon className="size-5 shrink-0" aria-hidden="true" /><span>{item}</span>{item === "Operations" && operationSections.length > 0 && <ChevronDown className={cn("ml-auto size-4 transition-transform", topic !== "Operations" && "-rotate-90")} aria-hidden="true" />}</Button>
                            {item === "Operations" && topic === "Operations" && operationSections.length > 0 && <div aria-label="Operations topics" className="ml-7 mt-1 space-y-0.5">{operationSections.map((section) => <Button key={section} variant="ghost" type="button" aria-current={topic === "Operations" && currentOperation === section ? "page" : undefined} onClick={() => { setTopic("Operations"); setOperation(section) }} className={cn("h-auto w-full justify-start rounded-lg px-3 py-2 text-sm font-normal", topic === "Operations" && currentOperation === section ? "font-medium text-primary" : "text-muted-foreground")}>{section}</Button>)}</div>}
                        </div>
                    })}</nav>
                    <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
                        <section aria-label={`${topic} permissions`} className="min-w-0 py-2 lg:px-2">
                            <div className="mb-7 flex items-center justify-between gap-3"><h2 className="text-3xl font-semibold tracking-tight">{topic === "Operations" ? currentOperation ?? topic : topic}</h2>{detail.data.protected && <span className="flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5 text-xs font-medium"><Lock className="size-3.5" />Protected</span>}</div>
                            {module && <section className="mb-7 border-b pb-7"><h3 className="mb-4 text-base font-semibold">Record scope</h3>
                                {!activePolicy ? <p className="rounded-xl bg-muted/60 p-4 text-sm text-muted-foreground">Record scope rules become available after the permission upgrade is reviewed and activated.</p> : scopes.isLoading ? <PermissionLoading /> : scopes.error ? <PermissionError error={scopes.error} retry={() => void scopes.refetch()} /> : rule ? <ScopeFields module={module} rule={rule} disabled={!editable || save.isPending} onChange={(next) => setScopeChanges((previous) => { const result = { ...previous }; if (JSON.stringify(next) === JSON.stringify(scopes.data?.[module])) delete result[module]; else result[module] = next; return result })} /> : <p className="text-sm text-muted-foreground">No scope rules available.</p>}
                            </section>}
                            {currentRows.length === 0 && <p className="py-5 text-sm text-muted-foreground">No configurable actions.</p>}
                            <div className="space-y-7">{Object.entries(sections).map(([section, rows]) => <section key={section} aria-label={section}><h3 className="mb-2 text-base font-semibold">{topic === "Operations" ? "Organization actions" : section}</h3><div className="divide-y">{rows.map((permission) => <label key={permission.key} className="flex min-h-12 items-center justify-between gap-5 py-3 text-sm">
                                <span>{permission.short_label || permission.label}{permission.developer_only && <Lock className="ml-2 inline size-3 text-muted-foreground" aria-label="Developer only" />}</span>
                                <Switch checked={changes[permission.key] ?? permission.is_granted} disabled={!editable || permission.configurable === false || save.isPending} onCheckedChange={(granted) => setChanges((previous) => { const next = { ...previous }; if (granted === permission.is_granted) delete next[permission.key]; else next[permission.key] = granted; return next })} />
                            </label>)}</div></section>)}</div>
                        </section>
                        <aside aria-label="Access preview" className="rounded-xl bg-[#f8f0f6] p-6 dark:bg-muted/30 xl:sticky xl:top-6 xl:min-h-[620px]">
                            <h3 className="flex items-center gap-2 text-lg font-semibold"><Eye className="size-6 text-[#45253f] dark:text-primary" />Access preview</h3>
                            <p className="mt-6 text-sm font-semibold text-primary">{topic === "Operations" ? currentOperation ?? topic : topic}</p>
                            {rule && <p className="mt-3 text-sm leading-relaxed">{scopeLabel(rule)}</p>}
                            <h4 className="mb-4 mt-6 border-t border-[#45253f]/10 pt-6 font-semibold dark:border-border">Allowed actions</h4>
                            {selectedActions.length ? <ul className="space-y-3 text-sm">{selectedActions.map((permission) => <li className="flex items-start gap-2" key={permission.key}><Check className="mt-0.5 size-4 shrink-0 text-primary" />{permissionPreviewLabel(permission, currentRows)}</li>)}</ul> : <p className="text-sm text-muted-foreground">No actions enabled.</p>}
                            {activePolicy && detail.data.included_features && <PermissionIncludedFeatures features={detail.data.included_features} />}
                            {detail.data.protected && <p className="mt-6 border-t pt-5 text-sm text-muted-foreground">This role’s baseline cannot be changed.</p>}
                        </aside>
                    </div>
                </div>}
            </>}
        </div>
        {dirty && <div className="sticky bottom-0 z-20 mt-auto flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-6 py-4 backdrop-blur-sm"><p className="text-sm text-muted-foreground">Unsaved changes</p><div className="flex gap-3"><Button variant="outline" disabled={save.isPending} onClick={discard}>Discard</Button><Button className="bg-[#45253f] text-white hover:bg-[#59334f] dark:bg-primary" disabled={save.isPending || !editable} onClick={() => setReviewOpen(true)}>Review changes</Button></div></div>}
        <Dialog open={reviewOpen} onOpenChange={(open) => { if (!save.isPending) setReviewOpen(open) }}><DialogContent><DialogHeader><DialogTitle>Review {ROLE_LABELS[role] || role} changes</DialogTitle></DialogHeader>
            <ul className="max-h-80 space-y-3 overflow-y-auto text-sm">{Object.entries(changes).filter(([key]) => allRows.some((row) => row.key === key)).map(([key, enabled]) => <li key={key} className="flex justify-between gap-4"><span>{allRows.find((row) => row.key === key)?.label ?? key}</span><span className={enabled ? "text-emerald-700" : "text-destructive"}>{enabled ? "Allow" : "Remove"}</span></li>)}{Object.entries(scopeChanges).map(([key, value]) => <li key={key}><span className="font-medium">{MODULE_LABELS[key as RecordModule]}</span><p className="mt-1 text-muted-foreground">{scopeLabel(value)}</p></li>)}</ul>
            {save.error && <PermissionError error={save.error} />}<DialogFooter><Button variant="outline" disabled={save.isPending} onClick={() => setReviewOpen(false)}>Back</Button><Button disabled={save.isPending || !editable} onClick={() => void apply()}>{save.isPending ? "Applying…" : "Apply changes"}</Button></DialogFooter>
        </DialogContent></Dialog>
        <Dialog open={pendingRole !== null} onOpenChange={(open) => { if (!open) setPendingRole(null) }}><DialogContent><DialogHeader><DialogTitle>Discard unsaved changes?</DialogTitle></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setPendingRole(null)}>Keep editing</Button><Button onClick={() => { discard(); setRole(pendingRole!); setPendingRole(null) }}>Discard changes</Button></DialogFooter></DialogContent></Dialog>
    </div>
}
