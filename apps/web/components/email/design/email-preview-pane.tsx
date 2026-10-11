"use client"

import { useState } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ChevronsUpDownIcon, Loader2Icon } from "lucide-react"

import { EmailHtmlFrame } from "@/components/email/design/email-html-frame"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { EmailPreviewVariableMode, EmailTemplatePreview } from "@/lib/api/email-templates"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { useSurrogates } from "@/lib/hooks/use-surrogates"
import { cn } from "@/lib/utils"

export type EmailPreviewRequest = {
    subject: string
    body: string
    variableMode: EmailPreviewVariableMode
    recordId: string | null
}

type Viewport = "desktop" | "mobile" | "both"

const MODE_LABELS: Record<EmailPreviewVariableMode, string> = {
    sample: "Sample",
    names: "Variable names",
    record: "Record",
}

const VIEWPORT_LABELS: Record<Viewport, string> = {
    desktop: "Desktop",
    mobile: "Mobile",
    both: "Both",
}

// Gmail clips messages larger than this and hides the rest behind a link.
export const GMAIL_CLIP_BYTES = 102 * 1024

type EmailPreviewPaneProps = {
    subject: string
    body: string
    /** Identifies the preview endpoint, e.g. ["org", scope]. */
    queryKey: readonly unknown[]
    load: (request: EmailPreviewRequest) => Promise<EmailTemplatePreview>
    modes?: EmailPreviewVariableMode[]
}

function isSafeLink(href: string) {
    return /^(https:|mailto:|tel:|#|\{\{)/i.test(href.trim())
}

export function previewChecks(preview: EmailTemplatePreview) {
    const parsed = new DOMParser().parseFromString(preview.html, "text/html")
    const hrefs = Array.from(parsed.querySelectorAll("a[href]"), (link) => link.getAttribute("href") ?? "")
    return {
        bytes: new TextEncoder().encode(preview.html).length,
        links: hrefs.length,
        unsafeLinks: hrefs.filter((href) => !isSafeLink(href)).length,
    }
}

function SurrogatePreviewPicker({
    value,
    label,
    onChange,
}: {
    value: string | null
    label: string | null
    onChange: (id: string, label: string) => void
}) {
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState("")
    const debouncedQuery = useDebouncedValue(query.trim(), 300)
    const surrogates = useSurrogates(
        { per_page: 20, include_archived: false, ...(debouncedQuery ? { q: debouncedQuery } : {}) },
        { enabled: open },
    )
    const items = surrogates.data?.items ?? []

    return (
        <Popover
            open={open}
            onOpenChange={(next) => {
                setOpen(next)
                if (!next) setQuery("")
            }}
        >
            <PopoverTrigger
                render={
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-haspopup="listbox"
                        aria-label={label ? `Preview record: ${label}` : "Choose a record"}
                        className="w-60 justify-between font-normal"
                    >
                        <span className={cn("truncate", !value && "text-muted-foreground")}>
                            {label ?? "Choose a record"}
                        </span>
                        <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
                    </Button>
                }
            />
            <PopoverContent className="w-72 gap-0 p-0" align="start">
                <Command shouldFilter={false}>
                    <CommandInput
                        placeholder="Search surrogates"
                        aria-label="Search surrogates"
                        value={query}
                        onValueChange={setQuery}
                    />
                    <CommandList className="max-h-64">
                        {items.length > 0 ? (
                            <CommandGroup heading="Surrogates">
                                {items.map((surrogate) => (
                                    <CommandItem
                                        key={surrogate.id}
                                        value={surrogate.id}
                                        onSelect={() => {
                                            onChange(
                                                surrogate.id,
                                                `${surrogate.full_name} · ${surrogate.surrogate_number}`,
                                            )
                                            setOpen(false)
                                        }}
                                    >
                                        <span className="min-w-0 flex-1 truncate">{surrogate.full_name}</span>{" "}
                                        <span className="text-xs tabular-nums text-muted-foreground">
                                            {surrogate.surrogate_number}
                                        </span>
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        ) : surrogates.isLoading ? (
                            <div role="status" className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                Loading surrogates…
                            </div>
                        ) : (
                            <CommandEmpty>
                                {surrogates.isError ? "Couldn't load surrogates. Try again." : "No surrogates found"}
                            </CommandEmpty>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    )
}

export function EmailPreviewPane({
    subject,
    body,
    queryKey,
    load,
    modes = ["sample", "names", "record"],
}: EmailPreviewPaneProps) {
    const [variableMode, setVariableMode] = useState<EmailPreviewVariableMode>("sample")
    const [record, setRecord] = useState<{ id: string; label: string } | null>(null)
    const [viewport, setViewport] = useState<Viewport>("both")
    const request: EmailPreviewRequest = {
        subject,
        body,
        variableMode,
        recordId: variableMode === "record" ? (record?.id ?? null) : null,
    }
    const debouncedRequest = useDebouncedValue(request, 300)
    const waitingForRecord = debouncedRequest.variableMode === "record" && !debouncedRequest.recordId
    const preview = useQuery({
        queryKey: ["email-template-preview", ...queryKey, debouncedRequest],
        queryFn: () => load(debouncedRequest),
        enabled: !waitingForRecord,
        placeholderData: keepPreviousData,
        staleTime: 30_000,
    })
    const checks = preview.data ? previewChecks(preview.data) : null

    return (
        <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-3 sm:px-6">
                <ToggleGroup
                    aria-label="Preview as"
                    variant="outline"
                    size="sm"
                    spacing={0}
                    value={[variableMode]}
                    onValueChange={(next) => {
                        const mode = (Array.isArray(next) ? next[0] : next) as EmailPreviewVariableMode | undefined
                        if (mode) setVariableMode(mode)
                    }}
                >
                    {modes.map((mode) => (
                        <ToggleGroupItem key={mode} value={mode}>
                            {MODE_LABELS[mode]}
                        </ToggleGroupItem>
                    ))}
                </ToggleGroup>
                {variableMode === "record" ? (
                    <SurrogatePreviewPicker
                        value={record?.id ?? null}
                        label={record?.label ?? null}
                        onChange={(id, label) => setRecord({ id, label })}
                    />
                ) : null}
                <span className="flex-1" />
                <ToggleGroup
                    aria-label="Viewport"
                    variant="outline"
                    size="sm"
                    spacing={0}
                    value={[viewport]}
                    onValueChange={(next) => {
                        const value = (Array.isArray(next) ? next[0] : next) as Viewport | undefined
                        if (value) setViewport(value)
                    }}
                >
                    {(Object.keys(VIEWPORT_LABELS) as Viewport[]).map((value) => (
                        <ToggleGroupItem key={value} value={value}>
                            {VIEWPORT_LABELS[value]}
                        </ToggleGroupItem>
                    ))}
                </ToggleGroup>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-muted/40 px-4 py-6 sm:px-6">
                {waitingForRecord ? (
                    <p className="mx-auto max-w-md text-center text-sm text-muted-foreground">Choose a record to preview.</p>
                ) : preview.isError && !preview.data ? (
                    <Alert variant="destructive" className="mx-auto max-w-xl">
                        <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                            <span>Preview could not load.</span>
                            <Button type="button" size="sm" variant="outline" onClick={() => void preview.refetch()}>
                                Retry
                            </Button>
                        </AlertDescription>
                    </Alert>
                ) : !preview.data ? (
                    <div role="status" className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
                        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                        Loading preview…
                    </div>
                ) : (
                    <div className="flex flex-wrap items-start justify-center gap-6" aria-busy={preview.isFetching}>
                        {viewport !== "mobile" ? (
                            <section
                                aria-label="Desktop preview"
                                className="w-full max-w-[680px] min-w-0 overflow-hidden rounded-lg border border-border bg-card"
                            >
                                <p className="border-b border-border px-4 py-3 font-medium">
                                    {preview.data.subject || "No subject"}
                                </p>
                                <EmailHtmlFrame html={preview.data.html} title="Desktop email preview" autoHeight minHeight={240} />
                            </section>
                        ) : null}
                        {viewport !== "desktop" ? (
                            <section
                                aria-label="Mobile preview"
                                className="w-[375px] max-w-full overflow-hidden rounded-[2rem] border border-border bg-card p-3 shadow-sm"
                            >
                                <div className="overflow-hidden rounded-[1.4rem] border border-border">
                                    <p className="border-b border-border px-3 py-2 text-sm font-medium">
                                        {preview.data.subject || "No subject"}
                                    </p>
                                    <EmailHtmlFrame
                                        html={preview.data.html}
                                        title="Mobile email preview"
                                        className="h-[620px]"
                                    />
                                </div>
                            </section>
                        ) : null}
                        {checks ? (
                            <aside
                                aria-label="Checks"
                                className="w-full max-w-[680px] rounded-lg border border-border bg-card p-4 text-sm xl:w-64"
                            >
                                <h2 className="mb-2 font-medium">Checks</h2>
                                <dl className="grid gap-2">
                                    <div>
                                        <dt className="text-muted-foreground">Variables</dt>
                                        <dd className={preview.data.unresolved_variables.length ? "text-destructive" : undefined}>
                                            {preview.data.unresolved_variables.length
                                                ? `Unknown: ${preview.data.unresolved_variables.join(", ")}`
                                                : "All known"}
                                        </dd>
                                    </div>
                                    <div>
                                        <dt className="text-muted-foreground">Size</dt>
                                        <dd className={checks.bytes > GMAIL_CLIP_BYTES ? "text-destructive" : undefined}>
                                            {`${Math.ceil(checks.bytes / 1024)} KB`}
                                            {checks.bytes > GMAIL_CLIP_BYTES ? ", Gmail clips over 102 KB" : null}
                                        </dd>
                                    </div>
                                    <div>
                                        <dt className="text-muted-foreground">Links</dt>
                                        <dd className={checks.unsafeLinks ? "text-destructive" : undefined}>
                                            {checks.unsafeLinks
                                                ? `${checks.links}, ${checks.unsafeLinks} not https`
                                                : checks.links}
                                        </dd>
                                    </div>
                                </dl>
                            </aside>
                        ) : null}
                    </div>
                )}
            </div>
        </div>
    )
}
