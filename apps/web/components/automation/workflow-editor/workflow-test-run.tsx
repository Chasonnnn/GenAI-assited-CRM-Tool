"use client"

import { useDeferredValue, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { FlaskConicalIcon, Loader2Icon, RotateCcwIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { WorkflowTestRunController } from "@/lib/workflows/use-workflow-test-run"
import { ENTITY_LABELS, fetchTestEntities, type TestEntitySuggestion } from "@/lib/workflows/test-entities"
import { cn } from "@/lib/utils"
import { ReasonButton } from "./reason-button"

function entityName(entityType: string): string {
    return (ENTITY_LABELS[entityType] ?? "Record ID").replace(/ ID$/, "")
}

/** Record search inside the open picker; mounts only while the popover is open. */
function TestRecordSearch({
    entityType,
    onPick,
}: {
    entityType: string
    onPick: (record: TestEntitySuggestion) => void
}) {
    const [query, setQuery] = useState("")
    const deferredQuery = useDeferredValue(query)
    const label = entityName(entityType).toLowerCase()
    const suggestions = useQuery({
        queryKey: ["workflow-test-entities", entityType, deferredQuery],
        queryFn: () => fetchTestEntities(entityType, deferredQuery),
        staleTime: 30 * 1000,
    })
    const records = suggestions.data ?? []

    return (
        <>
            <Input
                aria-label={`Search ${label}`}
                placeholder={`Search ${label}`}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                autoFocus
            />
            <ul aria-label="Records" className="max-h-64 space-y-0.5 overflow-y-auto">
                {suggestions.isLoading ? (
                    <li role="status" className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
                        <Loader2Icon aria-hidden="true" className="size-3.5 animate-spin" />
                        Searching…
                    </li>
                ) : suggestions.isError ? (
                    <li className="px-2 py-1.5 text-xs text-destructive">Couldn't load records.</li>
                ) : records.length === 0 ? (
                    <li className="px-2 py-1.5 text-xs text-muted-foreground">
                        {deferredQuery.trim() ? "No matches." : "Type to search."}
                    </li>
                ) : (
                    records.map((record) => (
                        <li key={record.id}>
                            <Button
                                unstyled
                                type="button"
                                className="flex w-full flex-col items-start rounded-lg px-2 py-1.5 text-left outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"
                                onClick={() => onPick(record)}
                            >
                                <span className="w-full truncate text-sm">{record.label}</span>
                                {record.meta ? (
                                    <span className="w-full truncate text-xs text-muted-foreground">{record.meta}</span>
                                ) : null}
                            </Button>
                        </li>
                    ))
                )}
            </ul>
        </>
    )
}

/** Header button that picks a record and dry runs the current draft against it. */
export function WorkflowTestRunButton({
    testRun,
    disabledReason,
}: {
    testRun: WorkflowTestRunController
    disabledReason: string | null
}) {
    const [open, setOpen] = useState(false)

    if (disabledReason) {
        return (
            <ReasonButton reason={disabledReason} variant="outline">
                <FlaskConicalIcon aria-hidden="true" />
                Test run
            </ReasonButton>
        )
    }

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger render={<Button variant="outline" size="sm" disabled={testRun.isPending} />}>
                {testRun.isPending ? (
                    <Loader2Icon aria-hidden="true" className="animate-spin" />
                ) : (
                    <FlaskConicalIcon aria-hidden="true" />
                )}
                Test run
            </PopoverTrigger>
            <PopoverContent align="end" className="w-80 gap-3 p-3">
                <TestRecordSearch
                    entityType={testRun.entityType}
                    onPick={(record) => {
                        setOpen(false)
                        testRun.start(record)
                    }}
                />
                <p className="text-xs text-muted-foreground">Dry run. Nothing is sent or changed.</p>
            </PopoverContent>
        </Popover>
    )
}

/** Floating summary of the last test run, with rerun and clear. */
export function WorkflowTestRunBar({ testRun, className }: { testRun: WorkflowTestRunController; className?: string }) {
    const { run, stepStates, isStale, isPending, pendingRecord, error } = testRun
    if (!run && !isPending && !error) return null

    const wouldRun = stepStates?.filter((state) => state === "would_run").length ?? 0
    const waits = stepStates?.includes("needs_approval") ?? false

    return (
        <div
            role="status"
            aria-live="polite"
            className={cn(
                "flex w-max max-w-[calc(100%-2rem)] flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border bg-popover/95 py-1.5 pr-1.5 pl-3 text-xs shadow-lg backdrop-blur animate-in fade-in-0 slide-in-from-bottom-2 motion-reduce:animate-none",
                className,
            )}
        >
            {isPending ? (
                <span className="flex items-center gap-2">
                    <Loader2Icon aria-hidden="true" className="size-3.5 animate-spin" />
                    Testing on {pendingRecord?.label ?? "the record"}…
                </span>
            ) : error ? (
                <span className="text-destructive">{error}</span>
            ) : run ? (
                <>
                    <span className="min-w-0 truncate font-medium">Tested on {run.record.label}</span>
                    {isStale ? (
                        <span className="text-amber-700 dark:text-amber-400">Changed since this test</span>
                    ) : (
                        <>
                            <span className={run.result.conditions_matched ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}>
                                {run.result.conditions_matched ? "Filters matched" : "Filters not matched"}
                            </span>
                            <span className="text-muted-foreground">
                                {wouldRun} of {run.result.actions_preview.length} steps would run
                                {waits ? ", then wait for approval" : ""}
                            </span>
                        </>
                    )}
                </>
            ) : null}
            <span className="ml-auto flex items-center">
                {run && !isPending ? (
                    <Button size="sm" variant="ghost" className="h-7" onClick={testRun.rerun}>
                        <RotateCcwIcon aria-hidden="true" />
                        Run again
                    </Button>
                ) : null}
                {!isPending ? (
                    <Button size="icon-sm" variant="ghost" className="size-7" aria-label="Clear test run" onClick={testRun.clear}>
                        <XIcon aria-hidden="true" />
                    </Button>
                ) : null}
            </span>
        </div>
    )
}
