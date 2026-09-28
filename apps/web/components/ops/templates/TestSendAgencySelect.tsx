"use client"

import { useQuery } from "@tanstack/react-query"

import { listOrganizations, type OrganizationSummary } from "@/lib/api/platform"
import { createSelectLabelGetter } from "@/lib/select-labels"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

const EMPTY_AGENCIES: OrganizationSummary[] = []

/** Active agencies for ops test sends. Deleted agencies cannot render org variables. */
export function useTestSendAgencies() {
    const query = useQuery({
        queryKey: ["platform", "organizations", "test-send"],
        queryFn: () => listOrganizations({ limit: 200 }),
        staleTime: 60_000,
        retry: false,
    })
    const agencies = (query.data?.items ?? EMPTY_AGENCIES).filter((agency) => !agency.deleted_at)
    return {
        agencies,
        isLoading: query.isLoading,
        isError: query.isError,
        refetch: query.refetch,
        /** The agency to use when the user has not picked one: the only agency, if there is one. */
        defaultAgencyId: agencies.length === 1 ? (agencies[0]?.id ?? "") : "",
    }
}

type TestSendAgencySelectProps = {
    id: string
    agencies: OrganizationSummary[]
    isLoading: boolean
    isError: boolean
    value: string
    onValueChange: (agencyId: string) => void
    invalid?: boolean
    describedBy?: string | undefined
}

export function TestSendAgencySelect({
    id,
    agencies,
    isLoading,
    isError,
    value,
    onValueChange,
    invalid = false,
    describedBy,
}: TestSendAgencySelectProps) {
    const getAgencyLabel = createSelectLabelGetter(
        agencies.map((agency) => ({ value: agency.id, label: agency.name })),
        { emptyLabel: "Select agency", unknownLabel: "Unknown agency" },
    )
    const placeholder = isLoading
        ? "Loading agencies…"
        : isError
          ? "Couldn't load agencies"
          : agencies.length === 0
            ? "No agencies"
            : "Select agency"

    return (
        <Select
            value={value}
            onValueChange={(next) => onValueChange(typeof next === "string" ? next : "")}
            disabled={isLoading || agencies.length === 0}
        >
            <SelectTrigger
                id={id}
                className="w-full"
                aria-invalid={invalid ? true : undefined}
                aria-describedby={describedBy}
            >
                <SelectValue placeholder={placeholder}>{getAgencyLabel}</SelectValue>
            </SelectTrigger>
            <SelectContent>
                {agencies.map((agency) => (
                    <SelectItem key={agency.id} value={agency.id}>
                        <span className="truncate">{agency.name}</span>
                        <span className="font-mono text-xs text-muted-foreground">{agency.slug}</span>
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}
