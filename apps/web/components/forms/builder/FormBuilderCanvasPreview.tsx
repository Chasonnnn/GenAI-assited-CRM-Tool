"use client"

import { useState } from "react"

import { Label } from "@/components/ui/label"
import {
    PublicFormFieldRenderer,
    isHalfWidthPublicField,
    type PublicFormAnswerValue,
} from "@/components/forms/PublicFormFieldRenderer"
import { PublicFormHeader } from "@/components/forms/PublicFormHeader"
import { FormBuilderFieldPreview } from "@/components/forms/FormBuilderFieldPreview"
import { buildFormSchema, type BuilderFormPage } from "@/lib/forms/form-builder-document"
import type { FormField } from "@/lib/api/forms"
import { cn } from "@/lib/utils"

type FormBuilderCanvasPreviewProps = {
    pages: BuilderFormPage[]
    publicEyebrow: string
    publicTitle: string
    publicSubtitle: string
    resolvedLogoUrl: string
    privacyNotice: string
    previewDevice: "desktop" | "mobile"
    desktopWidthClass: string
    mobileWidthClass: string
}

type PreviewAnswers = Record<string, PublicFormAnswerValue>

function isEmptyValue(value: PublicFormAnswerValue) {
    if (value === null || value === undefined) return true
    if (typeof value === "string") return value.trim() === ""
    if (Array.isArray(value)) return value.length === 0
    return false
}

function evaluateCondition(
    condition: FormField["show_if"],
    value: PublicFormAnswerValue,
) {
    if (!condition) return true
    const expected = condition.value
    switch (condition.operator) {
        case "is_empty":
            return isEmptyValue(value)
        case "is_not_empty":
            return !isEmptyValue(value)
        case "equals":
            if (expected !== undefined && expected !== null && typeof expected === "string") {
                return value !== null && value !== undefined ? String(value) === expected : false
            }
            return value === expected
        case "not_equals":
            if (expected !== undefined && expected !== null && typeof expected === "string") {
                return value !== null && value !== undefined ? String(value) !== expected : true
            }
            return value !== expected
        case "contains":
            if (Array.isArray(value)) {
                const list = value.filter((item): item is string => typeof item === "string")
                return expected ? list.includes(String(expected)) : false
            }
            if (typeof value === "string" && typeof expected === "string") {
                return value.includes(expected)
            }
            return false
        case "not_contains":
            if (Array.isArray(value)) {
                const list = value.filter((item): item is string => typeof item === "string")
                return expected ? !list.includes(String(expected)) : true
            }
            if (typeof value === "string" && typeof expected === "string") {
                return !value.includes(expected)
            }
            return true
        default:
            return true
    }
}

function isFieldVisible(field: FormField, answers: PreviewAnswers) {
    if (!field.show_if) return true
    const controllingValue = answers[field.show_if.field_key] ?? null
    return evaluateCondition(field.show_if, controllingValue)
}

function PreviewFallbackField({ field }: { field: FormField }) {
    return (
        <div className="space-y-2 rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
            <Label className="text-sm font-medium">
                {field.label} {field.required ? <span className="text-red-500">*</span> : null}
            </Label>
            <FormBuilderFieldPreview
                label={field.label}
                type={field.type}
                options={field.options?.map((option) => option.label)}
                columns={field.columns?.map((column) => ({
                    id: column.key,
                    label: column.label,
                    type: column.type,
                    required: column.required ?? false,
                    ...(column.options ? { options: column.options.map((option) => option.label) } : {}),
                }))}
                rows={field.rows?.map((row) => ({
                    id: row.key,
                    label: row.label,
                    ...(row.help_text ? { helpText: row.help_text } : {}),
                }))}
            />
            {field.help_text ? <p className="text-xs text-neutral-500">{field.help_text}</p> : null}
        </div>
    )
}

export function FormBuilderCanvasPreview({
    pages,
    publicEyebrow,
    publicTitle,
    publicSubtitle,
    resolvedLogoUrl,
    privacyNotice,
    previewDevice,
    desktopWidthClass,
    mobileWidthClass,
}: FormBuilderCanvasPreviewProps) {
    const [answers, setAnswers] = useState<PreviewAnswers>({})
    const [datePickerOpen, setDatePickerOpen] = useState<Record<string, boolean>>({})

    const previewSchema = buildFormSchema(pages, {
        publicEyebrow,
        publicTitle,
        publicSubtitle,
        logoUrl: resolvedLogoUrl,
        privacyNotice,
    })

    const sections = previewSchema.pages
        .map((page, pageIndex) => ({
            id: pages[pageIndex]?.id ?? pageIndex,
            title: page.title?.trim() || `Section ${pageIndex + 1}`,
            fields: page.fields.filter((field) => isFieldVisible(field, answers)),
        }))
        .filter((section) => section.fields.length > 0)

    const previewTitle = publicTitle.trim()
    const previewEyebrow = publicEyebrow.trim()
    const previewDescription = publicSubtitle.trim()

    return (
        <div
            data-testid="form-builder-preview-shell"
            className={cn(
                "mx-auto w-full overflow-hidden rounded-[28px] border border-border/70 bg-gradient-to-b from-neutral-50 to-neutral-100/70",
                previewDevice === "mobile" ? mobileWidthClass : desktopWidthClass,
            )}
        >
            <PublicFormHeader
                eyebrow={previewEyebrow}
                publicTitle={previewTitle}
                description={previewDescription}
                resolvedLogoUrl={resolvedLogoUrl || null}
                showLogo={Boolean(resolvedLogoUrl)}
                onLogoError={() => undefined}
                metadata="Preview"
            >
                <span className="inline-flex w-fit rounded-full border border-neutral-200 bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-neutral-500">
                    Builder preview
                </span>
            </PublicFormHeader>

            <div className="flex flex-col gap-6 px-4 pb-10 sm:px-6 lg:px-12">
                {sections.length > 0 ? (
                    sections.map((section) => (
                        <section
                            key={section.id}
                            aria-labelledby={`preview-section-${section.id}`}
                            className="flex flex-col gap-5 rounded-lg border border-neutral-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(23,23,23,0.05),0_8px_24px_rgba(23,23,23,0.04)] sm:p-8"
                        >
                            <h2 id={`preview-section-${section.id}`} className="text-xl font-semibold text-neutral-950">
                                {section.title}
                            </h2>
                            <div
                                className={cn(
                                    "grid gap-x-5 gap-y-6",
                                    previewDevice === "desktop" && "sm:grid-cols-2",
                                )}
                            >
                                {section.fields.map((field) => (
                                    <div
                                        key={field.key}
                                        className={cn(
                                            "min-w-0",
                                            !isHalfWidthPublicField(field) && "sm:col-span-2",
                                        )}
                                    >
                                        {["address", "file"].includes(field.type) ? (
                                            <PreviewFallbackField field={field} />
                                        ) : (
                                            <PublicFormFieldRenderer
                                                field={field}
                                                value={answers[field.key]}
                                                updateField={(fieldKey, value) =>
                                                    setAnswers((prev) => ({ ...prev, [fieldKey]: value }))
                                                }
                                                datePickerOpen={datePickerOpen}
                                                setDatePickerOpen={setDatePickerOpen}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        </section>
                    ))
                ) : (
                    <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-8 text-center">
                        <p className="text-base font-semibold text-neutral-900">Nothing to preview yet</p>
                    </div>
                )}

                {privacyNotice ? (
                    <p className="text-xs text-neutral-500">{privacyNotice}</p>
                ) : null}
            </div>
        </div>
    )
}
