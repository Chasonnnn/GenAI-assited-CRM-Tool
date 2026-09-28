"use client"

import { useState } from "react"
import { ChevronsUpDownIcon, Loader2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useAuth } from "@/lib/auth-context"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { useDonors } from "@/lib/hooks/use-donors"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useSurrogates } from "@/lib/hooks/use-surrogates"
import {
    getTaskRelatedRecords,
    type TaskRelatedRecordFields,
    type TaskRelatedRecordSelection,
} from "@/lib/task-related-record"
import { cn } from "@/lib/utils"

type RecordSegment = "all" | "surrogate" | "intended_parent" | "donor"

const RECORD_SEGMENTS: { value: RecordSegment; label: string }[] = [
    { value: "all", label: "All" },
    { value: "surrogate", label: "Surrogates" },
    { value: "intended_parent", label: "Intended Parents" },
    { value: "donor", label: "Donors" },
]

const isRecordSegment = (value: unknown): value is RecordSegment =>
    RECORD_SEGMENTS.some((segment) => segment.value === value)

const RECORD_VIEW_PERMISSIONS: Record<Exclude<RecordSegment, "all">, string> = {
    surrogate: "view_surrogates",
    intended_parent: "view_intended_parents",
    donor: "view_donors",
}

// Each type shows its first page; typing searches the server, so every record stays reachable.
const RESULTS_PER_TYPE = 20

type RecordOption = {
    value: TaskRelatedRecordSelection
    name: string
    detail: string | null
    number: string | null
    /** Trigger text, in the same "<Type> <number>" form the task lists use. */
    label: string
}

type RecordGroup = { heading: string; options: RecordOption[] }

function RecordOptionItem({ option, onSelect }: { option: RecordOption; onSelect: (option: RecordOption) => void }) {
    return (
        <CommandItem value={option.value} onSelect={() => onSelect(option)}>
            <span className="min-w-0 flex-1 truncate">
                {option.detail ? `${option.name} · ${option.detail}` : option.name}
            </span>
            {/* Keeps a space between the name and number in the option's accessible name. */}
            {" "}
            {option.number ? (
                <span className="text-xs tabular-nums text-muted-foreground">{option.number}</span>
            ) : null}
        </CommandItem>
    )
}

export function TaskRelatedRecordPicker({
    value,
    onValueChange,
    currentRecord,
}: {
    value: TaskRelatedRecordSelection
    onValueChange: (value: TaskRelatedRecordSelection) => void
    currentRecord?: TaskRelatedRecordFields
}) {
    const [open, setOpen] = useState(false)
    const [segment, setSegment] = useState<RecordSegment>("all")
    const [query, setQuery] = useState("")
    const [selectedOption, setSelectedOption] = useState<RecordOption | null>(null)
    const debouncedQuery = useDebouncedValue(query.trim(), 300)
    const searchParams = debouncedQuery ? { q: debouncedQuery } : {}

    // Record types the role cannot view are left out instead of failing with a 403. Until the
    // permission lookup succeeds every type is offered; the API still enforces access.
    const { user } = useAuth()
    const permissions = useEffectivePermissions(user?.user_id ?? null).data?.permissions
    const canView = (type: Exclude<RecordSegment, "all">) =>
        !permissions || permissions.includes(RECORD_VIEW_PERMISSIONS[type])
    const segments = RECORD_SEGMENTS.filter((option) => option.value === "all" || canView(option.value))
    const activeSegment = segments.some((option) => option.value === segment) ? segment : "all"

    const showSurrogates = open && canView("surrogate") && (activeSegment === "all" || activeSegment === "surrogate")
    const showIntendedParents =
        open && canView("intended_parent") && (activeSegment === "all" || activeSegment === "intended_parent")
    const showDonors = open && canView("donor") && (activeSegment === "all" || activeSegment === "donor")

    const surrogatesQuery = useSurrogates(
        { per_page: RESULTS_PER_TYPE, include_archived: false, ...searchParams },
        { enabled: showSurrogates },
    )
    const intendedParentsQuery = useIntendedParents(
        { per_page: RESULTS_PER_TYPE, ...searchParams },
        { enabled: showIntendedParents },
    )
    const eggDonorsQuery = useDonors(
        { donor_type: "egg", per_page: RESULTS_PER_TYPE, ...searchParams },
        { enabled: showDonors },
    )
    const spermDonorsQuery = useDonors(
        { donor_type: "sperm", per_page: RESULTS_PER_TYPE, ...searchParams },
        { enabled: showDonors },
    )

    const groups: RecordGroup[] = [
        {
            heading: "Surrogates",
            options: showSurrogates
                ? (surrogatesQuery.data?.items ?? []).map((surrogate) => ({
                    value: `surrogate:${surrogate.id}` as const,
                    name: surrogate.full_name,
                    detail: null,
                    number: surrogate.surrogate_number,
                    label: `Surrogate #${surrogate.surrogate_number} — ${surrogate.full_name}`,
                }))
                : [],
        },
        {
            heading: "Intended Parents",
            options: showIntendedParents
                ? (intendedParentsQuery.data?.items ?? []).map((intendedParent) => ({
                    value: `intended_parent:${intendedParent.id}` as const,
                    name: intendedParent.full_name,
                    detail: null,
                    number: intendedParent.intended_parent_number,
                    label: `Intended Parent ${intendedParent.intended_parent_number} — ${intendedParent.full_name}`,
                }))
                : [],
        },
        {
            heading: "Donors",
            options: showDonors
                ? [
                    ...(eggDonorsQuery.data?.items ?? []).map((donor) => ({
                        value: `donor:${donor.id}` as const,
                        name: donor.full_name,
                        detail: "Egg Donor",
                        number: donor.donor_number,
                        label: `Egg Donor ${donor.donor_number} — ${donor.full_name}`,
                    })),
                    ...(spermDonorsQuery.data?.items ?? []).map((donor) => ({
                        value: `donor:${donor.id}` as const,
                        name: donor.full_name,
                        detail: "Sperm Donor",
                        number: donor.donor_number,
                        label: `Sperm Donor ${donor.donor_number} — ${donor.full_name}`,
                    })),
                ]
                : [],
        },
    ]
    const visibleGroups = groups.filter((group) => group.options.length > 0)
    const isFetching =
        (showSurrogates && surrogatesQuery.isLoading)
        || (showIntendedParents && intendedParentsQuery.isLoading)
        || (showDonors && (eggDonorsQuery.isLoading || spermDonorsQuery.isLoading))
    const hasError =
        (showSurrogates && surrogatesQuery.isError)
        || (showIntendedParents && intendedParentsQuery.isError)
        || (showDonors && (eggDonorsQuery.isError || spermDonorsQuery.isError))

    const currentRecordLabel = currentRecord
        ? getTaskRelatedRecords(currentRecord).find((record) => `${record.kind}:${record.id}` === value)?.label
        : undefined
    const selectedLabel =
        value === "none"
            ? null
            : selectedOption?.value === value
                ? selectedOption.label
                : currentRecordLabel
                    ?? groups.flatMap((group) => group.options).find((option) => option.value === value)?.label
                    ?? "Linked record"

    const handleOpenChange = (nextOpen: boolean) => {
        setOpen(nextOpen)
        if (!nextOpen) setQuery("")
    }

    const selectOption = (option: RecordOption | null) => {
        setSelectedOption(option)
        onValueChange(option?.value ?? "none")
        handleOpenChange(false)
    }

    return (
        <div className="space-y-2">
            <Label id="task-related-record-label" htmlFor="task-related-record">Linked record</Label>
            <Popover open={open} onOpenChange={handleOpenChange}>
                <PopoverTrigger
                    render={
                        <Button
                            id="task-related-record"
                            type="button"
                            variant="outline"
                            aria-haspopup="listbox"
                            aria-labelledby="task-related-record-label task-related-record"
                            className="w-full justify-between font-normal"
                        >
                            <span className={cn("truncate", !selectedLabel && "text-muted-foreground")}>
                                {selectedLabel ?? "No linked record"}
                            </span>
                            <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
                        </Button>
                    }
                />
                <PopoverContent className="w-(--anchor-width) gap-0 p-0" align="start">
                    <Command shouldFilter={false}>
                        <CommandInput
                            placeholder="Search records"
                            aria-label="Search records"
                            value={query}
                            onValueChange={setQuery}
                        />
                        <ToggleGroup
                            aria-label="Record type"
                            variant="outline"
                            size="sm"
                            spacing={1}
                            value={[activeSegment]}
                            onValueChange={(next) => {
                                const nextSegment = Array.isArray(next) ? next[0] : next
                                if (isRecordSegment(nextSegment)) setSegment(nextSegment)
                            }}
                            className="w-full flex-wrap border-b p-2"
                        >
                            {segments.map((option) => (
                                <ToggleGroupItem key={option.value} value={option.value}>
                                    {option.label}
                                </ToggleGroupItem>
                            ))}
                        </ToggleGroup>
                        <CommandList className="max-h-64">
                            {!debouncedQuery && value !== "none" ? (
                                <CommandGroup>
                                    <CommandItem value="none" onSelect={() => selectOption(null)}>
                                        No linked record
                                    </CommandItem>
                                </CommandGroup>
                            ) : null}
                            {visibleGroups.map((group) => (
                                <CommandGroup key={group.heading} heading={group.heading}>
                                    {group.options.map((option) => (
                                        <RecordOptionItem key={option.value} option={option} onSelect={selectOption} />
                                    ))}
                                </CommandGroup>
                            ))}
                            {visibleGroups.length === 0 ? (
                                isFetching ? (
                                    <div role="status" className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                                        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                        Loading records…
                                    </div>
                                ) : (
                                    <CommandEmpty>{hasError ? "Couldn't load records. Try again." : "No records found"}</CommandEmpty>
                                )
                            ) : null}
                        </CommandList>
                    </Command>
                </PopoverContent>
            </Popover>
        </div>
    )
}
