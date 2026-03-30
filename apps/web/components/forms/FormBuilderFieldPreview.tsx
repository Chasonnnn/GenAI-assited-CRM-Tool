"use client"

import type { ReactNode } from "react"
import { ChevronDownIcon, UploadIcon } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { FieldType, FormFieldColumn, FormFieldValidation } from "@/lib/api/forms"
import { getBuilderOptionLabel, getBuilderOptionValue, type BuilderFormField } from "@/lib/forms/form-builder-document"
import { cn } from "@/lib/utils"

type PreviewColumn = {
    id: string
    label: string
    type: FormFieldColumn["type"]
    required: boolean
    options?: string[]
    validation?: FormFieldValidation | null
}

type PreviewRow = {
    id: string
    label: string
    helpText?: string
}

type FormBuilderFieldPreviewProps = {
    label: string
    type: FieldType
    surrogateFieldMapping?: string | undefined
    options?: BuilderFormField["options"] | undefined
    columns?: PreviewColumn[] | undefined
    rows?: PreviewRow[] | undefined
    className?: string
}

function PreviewBox({
    children,
    className,
}: {
    children: ReactNode
    className?: string
}) {
    return (
        <div
            className={cn(
                "flex h-11 items-center rounded-xl border border-border/70 bg-background/85 px-3 text-sm text-muted-foreground shadow-none",
                className,
            )}
        >
            {children}
        </div>
    )
}

function getPreviewPlaceholder(type: FieldType, label: string, surrogateFieldMapping?: string) {
    const normalized = `${surrogateFieldMapping ?? ""} ${label}`.toLowerCase()
    if (normalized.includes("full_name") || normalized.includes("full name")) {
        return "Enter full name"
    }
    if (normalized.includes("email")) {
        return "name@example.com"
    }
    if (normalized.includes("phone")) {
        return "(555) 555-5555"
    }
    if (normalized.includes("weight")) {
        return "Enter pounds"
    }
    if (type === "number") {
        return "Enter number"
    }
    if (type === "textarea") {
        return "Add more detail"
    }
    return "Type your answer"
}

export function FormBuilderFieldPreview({
    label,
    type,
    surrogateFieldMapping,
    options,
    columns,
    rows,
    className,
}: FormBuilderFieldPreviewProps) {
    const previewOptions = options && options.length > 0 ? options : ["Option 1", "Option 2"]
    const previewColumns =
        columns && columns.length > 0
            ? columns
            : [
                { id: "column-1", label: "Column 1", type: "text" as const, required: false },
                { id: "column-2", label: "Column 2", type: "text" as const, required: false },
            ]
    const previewRows =
        rows && rows.length > 0
            ? rows
            : [
                { id: "row-1", label: "Item 1" },
                { id: "row-2", label: "Item 2" },
            ]

    return (
        <div
            role="group"
            aria-label={`Preview answer for ${label}`}
            className={cn(
                "pointer-events-none mt-2 rounded-2xl border border-border/60 bg-muted/20 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]",
                className,
            )}
        >
            {type === "textarea" && (
                <Textarea
                    disabled
                    placeholder={getPreviewPlaceholder(type, label, surrogateFieldMapping)}
                    className="min-h-24 resize-none rounded-xl border-border/70 bg-background/85 shadow-none"
                />
            )}

            {(type === "text" || type === "email" || type === "phone" || type === "number") && (
                <Input
                    disabled
                    placeholder={getPreviewPlaceholder(type, label, surrogateFieldMapping)}
                    className="h-11 rounded-xl border-border/70 bg-background/85 shadow-none"
                />
            )}

            {type === "date" && (
                <div className="grid grid-cols-3 gap-2">
                    <PreviewBox>Month</PreviewBox>
                    <PreviewBox>Day</PreviewBox>
                    <PreviewBox>Year</PreviewBox>
                </div>
            )}

            {type === "height" && (
                <div className="grid grid-cols-2 gap-2">
                    <PreviewBox>Feet</PreviewBox>
                    <PreviewBox>Inches</PreviewBox>
                </div>
            )}

            {type === "select" && (
                <PreviewBox className="justify-between">
                    <span>Select an option</span>
                    <ChevronDownIcon className="size-4" />
                </PreviewBox>
            )}

            {(type === "radio" || type === "checkbox" || type === "multiselect") && (
                <div className="grid gap-2 sm:grid-cols-2">
                    {previewOptions.slice(0, 4).map((option) => (
                        <div
                            key={getBuilderOptionValue(option)}
                            className="flex h-11 items-center gap-3 rounded-xl border border-border/70 bg-background/85 px-3 text-sm"
                        >
                            <span className="size-4 rounded-full border border-border bg-background" />
                            <span className="text-foreground">{getBuilderOptionLabel(option)}</span>
                        </div>
                    ))}
                </div>
            )}

            {type === "address" && (
                <div className="space-y-2">
                    <PreviewBox>Street address</PreviewBox>
                    <div className="grid grid-cols-3 gap-2">
                        <PreviewBox className="col-span-1">City</PreviewBox>
                        <PreviewBox className="col-span-1">State</PreviewBox>
                        <PreviewBox className="col-span-1">ZIP</PreviewBox>
                    </div>
                </div>
            )}

            {type === "file" && (
                <div className="flex h-24 flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 bg-background/80 text-center">
                    <UploadIcon className="mb-2 size-4 text-muted-foreground" />
                    <div className="text-sm font-medium text-foreground">Upload file</div>
                    <div className="text-xs text-muted-foreground">PDF, JPG, or PNG</div>
                </div>
            )}

            {type === "repeatable_table" && (
                <div className="overflow-hidden rounded-2xl border border-border/70 bg-background/85">
                    <div className="grid grid-cols-2 border-b border-border/70 bg-muted/30 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
                        {previewColumns.slice(0, 2).map((column) => (
                            <div key={column.id} className="px-3 py-2">
                                {column.label}
                            </div>
                        ))}
                    </div>
                    <div className="grid grid-cols-2">
                        {previewColumns.slice(0, 2).map((column) => (
                            <div key={column.id} className="border-r border-border/70 px-3 py-3 last:border-r-0">
                                <div className="h-4 rounded-full bg-muted/70" />
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {type === "table" && (
                <div className="space-y-2">
                    {previewRows.slice(0, 2).map((row) => (
                        <div key={row.id} className="rounded-2xl border border-border/70 bg-background/85 p-3">
                            <div className="mb-3 text-sm font-medium text-foreground">{row.label}</div>
                            <div className="grid gap-2 md:grid-cols-2">
                                {previewColumns.slice(0, 2).map((column) => (
                                    <div key={column.id} className="space-y-2">
                                        <div className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
                                            {column.label}
                                        </div>
                                        {column.type === "radio" ? (
                                            <div className="grid grid-cols-2 gap-2">
                                                {(column.options && column.options.length > 0 ? column.options : ["No", "Yes"])
                                                    .slice(0, 2)
                                                    .map((option) => (
                                                        <PreviewBox key={option}>{option}</PreviewBox>
                                                    ))}
                                            </div>
                                        ) : column.type === "textarea" ? (
                                            <Input
                                                disabled
                                                type="text"
                                                placeholder="Add details"
                                                className="h-11 rounded-xl border-border/70 bg-background/85 shadow-none"
                                            />
                                        ) : column.type === "select" ? (
                                            <PreviewBox className="justify-between">
                                                <span>Select</span>
                                                <ChevronDownIcon className="size-4" />
                                            </PreviewBox>
                                        ) : (
                                            <Input
                                                disabled
                                                type={column.type === "number" ? "number" : column.type === "date" ? "date" : "text"}
                                                placeholder={column.label}
                                                className="h-11 rounded-xl border-border/70 bg-background/85 shadow-none"
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
