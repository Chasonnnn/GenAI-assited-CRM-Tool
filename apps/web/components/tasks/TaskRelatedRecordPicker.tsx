"use client"

import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useDonors } from "@/lib/hooks/use-donors"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"
import { useSurrogates } from "@/lib/hooks/use-surrogates"
import {
    getTaskRelatedRecords,
    type TaskRelatedRecordFields,
    type TaskRelatedRecordSelection,
} from "@/lib/task-related-record"

export function TaskRelatedRecordPicker({
    value,
    onValueChange,
    currentRecord,
}: {
    value: TaskRelatedRecordSelection
    onValueChange: (value: TaskRelatedRecordSelection) => void
    currentRecord?: TaskRelatedRecordFields
}) {
    const surrogatesQuery = useSurrogates({ per_page: 100, include_archived: false })
    const intendedParentsQuery = useIntendedParents({ per_page: 100 })
    const eggDonorsQuery = useDonors({ donor_type: "egg", per_page: 100 })
    const spermDonorsQuery = useDonors({ donor_type: "sperm", per_page: 100 })

    const options = [
        ...(surrogatesQuery.data?.items ?? []).map((surrogate) => ({
            value: `surrogate:${surrogate.id}` as TaskRelatedRecordSelection,
            label: `Surrogate #${surrogate.surrogate_number} — ${surrogate.full_name}`,
        })),
        ...(intendedParentsQuery.data?.items ?? []).map((intendedParent) => ({
            value: `intended_parent:${intendedParent.id}` as TaskRelatedRecordSelection,
            label: `Intended Parent ${intendedParent.intended_parent_number} — ${intendedParent.full_name}`,
        })),
        ...(eggDonorsQuery.data?.items ?? []).map((donor) => ({
            value: `donor:${donor.id}` as TaskRelatedRecordSelection,
            label: `Egg Donor ${donor.donor_number} — ${donor.full_name}`,
        })),
        ...(spermDonorsQuery.data?.items ?? []).map((donor) => ({
            value: `donor:${donor.id}` as TaskRelatedRecordSelection,
            label: `Sperm Donor ${donor.donor_number} — ${donor.full_name}`,
        })),
    ]

    const hasCurrentOption = options.some((option) => option.value === value)
    if (!hasCurrentOption && value !== "none" && currentRecord) {
        const current = getTaskRelatedRecords(currentRecord)[0]
        if (current) options.unshift({ value, label: current.label })
    }

    return (
        <div className="space-y-2">
            <Label htmlFor="task-related-record">Linked record</Label>
            <Select
                value={value}
                onValueChange={(nextValue) => {
                    if (typeof nextValue === "string") {
                        onValueChange(nextValue as TaskRelatedRecordSelection)
                    }
                }}
            >
                <SelectTrigger id="task-related-record">
                    <SelectValue placeholder="No linked record" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="none">No linked record</SelectItem>
                    {options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}
