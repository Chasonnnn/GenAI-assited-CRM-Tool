"use client"

import { startTransition, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { listOrganizations, type OrganizationSummary } from "@/lib/api/platform"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Building2Icon, GlobeIcon, Loader2Icon, SearchIcon } from "lucide-react"

type PublishDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    onPublish: (publishAll: boolean, orgIds: string[]) => void
    isLoading?: boolean
    title?: string
    description?: string
    defaultPublishAll?: boolean
    initialOrgIds?: string[]
}

const EMPTY_ORG_IDS: string[] = []
const MODE_ALL_ID = "publish-dialog-mode-all"
const MODE_SELECTED_ID = "publish-dialog-mode-selected"
const SELECT_ALL_ID = "publish-dialog-select-all"

type PublishDialogState = {
    mode: "all" | "selected"
    search: string
    selectedOrgIds: string[]
}

function createPublishDialogState(defaultPublishAll: boolean, initialOrgIds: string[]): PublishDialogState {
    return {
        mode: defaultPublishAll ? "all" : "selected",
        search: "",
        selectedOrgIds: [...initialOrgIds],
    }
}

export function PublishDialog({
    open,
    onOpenChange,
    onPublish,
    isLoading = false,
    title = "Publish template",
    description = "Choose which organizations should see this template in their library. Publishing never overwrites org copies.",
    defaultPublishAll = true,
    initialOrgIds = EMPTY_ORG_IDS,
}: PublishDialogProps) {
    const [state, setDialogState] = useState(() => createPublishDialogState(defaultPublishAll, initialOrgIds))

    useEffect(() => {
        if (!open) return
        startTransition(() => {
            setDialogState(createPublishDialogState(defaultPublishAll, initialOrgIds))
        })
    }, [open, defaultPublishAll, initialOrgIds])

    const { data, isLoading: orgsLoading } = useQuery({
        queryKey: ["platform-orgs", "publish-dialog"],
        queryFn: () => listOrganizations({ limit: 200 }),
        enabled: open,
    })

    const organizations = (data?.items ?? []).filter((org) => !org.deleted_at)
    const query = state.search.trim().toLowerCase()
    const filteredOrgs = query
        ? organizations.filter((org) =>
              org.name.toLowerCase().includes(query) || org.slug.toLowerCase().includes(query)
          )
        : organizations

    const selectedSet = new Set(state.selectedOrgIds)
    const allFilteredSelected =
        filteredOrgs.length > 0 && filteredOrgs.every((org) => selectedSet.has(org.id))

    const toggleSelectAll = () => {
        setDialogState((current) => {
            if (allFilteredSelected) {
                const remaining = current.selectedOrgIds.filter((id) => !filteredOrgs.some((org) => org.id === id))
                return { ...current, selectedOrgIds: remaining }
            }
            const merged = new Set(current.selectedOrgIds)
            filteredOrgs.forEach((org) => merged.add(org.id))
            return { ...current, selectedOrgIds: Array.from(merged) }
        })
    }

    const toggleOrg = (orgId: string, checked: boolean) => {
        setDialogState((current) => {
            if (checked) {
                return { ...current, selectedOrgIds: Array.from(new Set([...current.selectedOrgIds, orgId])) }
            }
            return { ...current, selectedOrgIds: current.selectedOrgIds.filter((id) => id !== orgId) }
        })
    }

    const canPublish = state.mode === "all" || state.selectedOrgIds.length > 0

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <RadioGroup
                        value={state.mode}
                        onValueChange={(value) =>
                            setDialogState((current) => ({
                                ...current,
                                mode: value as "all" | "selected",
                            }))
                        }
                        className="space-y-3"
                    >
                        <label htmlFor={MODE_ALL_ID} className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem id={MODE_ALL_ID} value="all" />
                            <div className="space-y-1">
                                <div className="flex items-center gap-2 font-medium">
                                    <GlobeIcon className="size-4 text-teal-500" />
                                    Publish to all organizations
                                    <Badge variant="secondary">Global</Badge>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    Adds or updates the template in every org’s library.
                                </p>
                            </div>
                        </label>
                        <label htmlFor={MODE_SELECTED_ID} className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem id={MODE_SELECTED_ID} value="selected" />
                            <div className="space-y-1">
                                <div className="flex items-center gap-2 font-medium">
                                    <Building2Icon className="size-4 text-stone-500" />
                                    Publish to selected organizations
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    Only selected orgs will see this template in their library.
                                </p>
                            </div>
                        </label>
                    </RadioGroup>

                    {state.mode === "selected" && (
                        <div className="space-y-3">
                            <div className="relative">
                                <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    placeholder="Search organizations…"
                                    value={state.search}
                                    onChange={(event) =>
                                        setDialogState((current) => ({
                                            ...current,
                                            search: event.target.value,
                                        }))
                                    }
                                    className="pl-9"
                                />
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <Label htmlFor={SELECT_ALL_ID} className="flex items-center gap-2">
                                    <Checkbox
                                        id={SELECT_ALL_ID}
                                        checked={allFilteredSelected}
                                        onCheckedChange={() => toggleSelectAll()}
                                    />
                                    Select all
                                </Label>
                                <span className="text-muted-foreground">
                                    {state.selectedOrgIds.length} selected
                                </span>
                            </div>

                            <div className="rounded-lg border">
                                <ScrollArea className="h-56">
                                    {orgsLoading ? (
                                        <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                                            <Loader2Icon className="size-4 animate-spin" />
                                            Loading organizations…
                                        </div>
                                    ) : filteredOrgs.length === 0 ? (
                                        <div className="p-4 text-sm text-muted-foreground">
                                            No organizations match your search.
                                        </div>
                                    ) : (
                                        <div className="divide-y">
                                            {filteredOrgs.map((org: OrganizationSummary) => {
                                                const checked = selectedSet.has(org.id)
                                                const checkboxId = `publish-dialog-org-${org.id}`
                                                return (
                                                    <label
                                                        htmlFor={checkboxId}
                                                        key={org.id}
                                                        className="flex items-center justify-between gap-3 p-3 text-sm hover:bg-stone-50 dark:hover:bg-stone-800/40"
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <Checkbox
                                                                id={checkboxId}
                                                                checked={checked}
                                                                onCheckedChange={(next) =>
                                                                    toggleOrg(org.id, next === true)
                                                                }
                                                            />
                                                            <div>
                                                                <div className="font-medium text-stone-900 dark:text-stone-100">
                                                                    {org.name}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground">
                                                                    {org.slug}
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <Badge variant="outline" className="text-xs">
                                                            {org.subscription_plan}
                                                        </Badge>
                                                    </label>
                                                )
                                            })}
                                        </div>
                                    )}
                                </ScrollArea>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter className="flex flex-col gap-2 sm:flex-row sm:justify-between">
                    {state.mode === "selected" && !canPublish && (
                        <span className="text-xs text-amber-600">
                            Select at least one organization to continue.
                        </span>
                    )}
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={() => onPublish(state.mode === "all", state.selectedOrgIds)}
                            disabled={!canPublish || isLoading}
                        >
                            {isLoading && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Publish
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
