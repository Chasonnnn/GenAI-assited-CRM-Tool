"use client"

import { useEffect, useMemo, useState } from "react"
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

export function PublishDialog({
    open,
    onOpenChange,
    onPublish,
    isLoading = false,
    title = "Publish template",
    description = "Choose which organizations should see this template in their library. Publishing never overwrites org copies.",
    defaultPublishAll = true,
    initialOrgIds = [],
}: PublishDialogProps) {
    const [mode, setMode] = useState<"all" | "selected">(defaultPublishAll ? "all" : "selected")
    const [search, setSearch] = useState("")
    const [selectedOrgIds, setSelectedOrgIds] = useState<string[]>(initialOrgIds)

    useEffect(() => {
        if (!open) return
        setMode(defaultPublishAll ? "all" : "selected")
        setSelectedOrgIds(initialOrgIds)
        setSearch("")
    }, [open, defaultPublishAll, initialOrgIds])

    const { data, isLoading: orgsLoading } = useQuery({
        queryKey: ["platform-orgs", "publish-dialog"],
        queryFn: () => listOrganizations({ limit: 200 }),
        enabled: open,
    })

    const organizations = useMemo(
        () => (data?.items ?? []).filter((org) => !org.deleted_at),
        [data?.items]
    )

    const filteredOrgs = useMemo(() => {
        const query = search.trim().toLowerCase()
        if (!query) return organizations
        return organizations.filter((org) =>
            org.name.toLowerCase().includes(query) || org.slug.toLowerCase().includes(query)
        )
    }, [organizations, search])

    const selectedSet = useMemo(() => new Set(selectedOrgIds), [selectedOrgIds])
    const allFilteredSelected =
        filteredOrgs.length > 0 && filteredOrgs.every((org) => selectedSet.has(org.id))

    const toggleSelectAll = () => {
        if (allFilteredSelected) {
            const remaining = selectedOrgIds.filter((id) => !filteredOrgs.some((org) => org.id === id))
            setSelectedOrgIds(remaining)
        } else {
            const merged = new Set(selectedOrgIds)
            filteredOrgs.forEach((org) => merged.add(org.id))
            setSelectedOrgIds(Array.from(merged))
        }
    }

    const toggleOrg = (orgId: string, checked: boolean) => {
        setSelectedOrgIds((prev) => {
            if (checked) return Array.from(new Set([...prev, orgId]))
            return prev.filter((id) => id !== orgId)
        })
    }

    const canPublish = mode === "all" || selectedOrgIds.length > 0

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <RadioGroup
                        value={mode}
                        onValueChange={(value) => setMode(value as "all" | "selected")}
                        className="space-y-3"
                    >
                        <label className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem value="all" />
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
                        <label className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem value="selected" />
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

                    {mode === "selected" && (
                        <div className="space-y-3">
                            <div className="relative">
                                <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    placeholder="Search organizations..."
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    className="pl-9"
                                />
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <Label className="flex items-center gap-2">
                                    <Checkbox
                                        checked={allFilteredSelected}
                                        onCheckedChange={() => toggleSelectAll()}
                                    />
                                    Select all
                                </Label>
                                <span className="text-muted-foreground">
                                    {selectedOrgIds.length} selected
                                </span>
                            </div>

                            <div className="rounded-lg border">
                                <ScrollArea className="h-56">
                                    {orgsLoading ? (
                                        <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                                            <Loader2Icon className="size-4 animate-spin" />
                                            Loading organizations...
                                        </div>
                                    ) : filteredOrgs.length === 0 ? (
                                        <div className="p-4 text-sm text-muted-foreground">
                                            No organizations match your search.
                                        </div>
                                    ) : (
                                        <div className="divide-y">
                                            {filteredOrgs.map((org: OrganizationSummary) => {
                                                const checked = selectedSet.has(org.id)
                                                return (
                                                    <label
                                                        key={org.id}
                                                        className="flex items-center justify-between gap-3 p-3 text-sm hover:bg-stone-50 dark:hover:bg-stone-800/40"
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <Checkbox
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
                    {mode === "selected" && !canPublish && (
                        <span className="text-xs text-amber-600">
                            Select at least one organization to continue.
                        </span>
                    )}
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={() => onPublish(mode === "all", selectedOrgIds)}
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
