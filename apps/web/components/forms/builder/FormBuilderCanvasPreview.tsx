"use client"

import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { PublicFormFieldRenderer, type PublicFormAnswerValue } from "@/components/forms/PublicFormFieldRenderer"
import { PublicFormHeader } from "@/components/forms/PublicFormHeader"
import { FormBuilderFieldPreview } from "@/components/forms/FormBuilderFieldPreview"
import { buildFormSchema, type BuilderFormPage } from "@/lib/forms/form-builder-document"
import type { FormField } from "@/lib/api/forms"
import { cn } from "@/lib/utils"

type FormBuilderCanvasPreviewProps = {
    pages: BuilderFormPage[]
    activePage: number
    formName: string
    formDescription: string
    publicTitle: string
    resolvedLogoUrl: string
    privacyNotice: string
    previewDevice: "desktop" | "mobile"
    desktopWidthClass: string
    mobileWidthClass: string
    onSetActivePage: (pageId: number) => void
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
        <div className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
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
            {field.help_text ? <p className="text-xs text-stone-500">{field.help_text}</p> : null}
        </div>
    )
}

export function FormBuilderCanvasPreview({
    pages,
    activePage,
    formName,
    formDescription,
    publicTitle,
    resolvedLogoUrl,
    privacyNotice,
    previewDevice,
    desktopWidthClass,
    mobileWidthClass,
    onSetActivePage,
}: FormBuilderCanvasPreviewProps) {
    const [answers, setAnswers] = useState<PreviewAnswers>({})
    const [datePickerOpen, setDatePickerOpen] = useState<Record<string, boolean>>({})

    const previewSchema = useMemo(
        () =>
            buildFormSchema(pages, {
                publicTitle,
                logoUrl: resolvedLogoUrl,
                privacyNotice,
            }),
        [pages, privacyNotice, publicTitle, resolvedLogoUrl],
    )

    const activeIndex = Math.max(0, pages.findIndex((page) => page.id === activePage))
    const previewPage = previewSchema.pages[activeIndex]
    const currentPage = pages[activeIndex]
    const canGoBack = activeIndex > 0
    const canGoForward = activeIndex < pages.length - 1

    const visibleFields = useMemo(
        () => (previewPage?.fields ?? []).filter((field) => isFieldVisible(field, answers)),
        [answers, previewPage?.fields],
    )

    const previewTitle = publicTitle.trim() || formName.trim() || "Untitled Form"
    const previewDescription =
        formDescription.trim() || "Preview how applicants will experience this page."

    return (
        <div
            data-testid="form-builder-preview-shell"
            className={cn(
                "mx-auto w-full rounded-[28px] border border-border/70 bg-gradient-to-b from-stone-50 to-stone-100/70",
                previewDevice === "mobile" ? mobileWidthClass : desktopWidthClass,
            )}
        >
            <PublicFormHeader
                publicTitle={previewTitle}
                description={previewDescription}
                resolvedLogoUrl={resolvedLogoUrl || null}
                showLogo={Boolean(resolvedLogoUrl)}
                onLogoError={() => undefined}
                metadata={
                    <span>
                        Page {activeIndex + 1} of {Math.max(1, pages.length)}
                    </span>
                }
            >
                <span className="inline-flex rounded-full border border-stone-200 bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-500">
                    Builder preview
                </span>
            </PublicFormHeader>

            <div className="mx-auto max-w-3xl px-4 pb-8">
                <div className="min-h-[58rem] rounded-[24px] border border-stone-200/80 bg-white/95 p-5 md:p-6">
                    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-stone-200/80 pb-4">
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">
                                Active page
                            </p>
                            <h2 className="mt-1.5 text-lg font-semibold text-stone-900">
                                {currentPage?.name || `Page ${activeIndex + 1}`}
                            </h2>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => canGoBack && onSetActivePage(pages[activeIndex - 1]?.id ?? activePage)}
                                disabled={!canGoBack}
                            >
                                Previous
                            </Button>
                            <Button
                                type="button"
                                onClick={() =>
                                    canGoForward ? onSetActivePage(pages[activeIndex + 1]?.id ?? activePage) : undefined
                                }
                                disabled={!canGoForward}
                            >
                                {canGoForward ? "Next" : "Final page"}
                            </Button>
                        </div>
                    </div>

                    <div className="space-y-4">
                        {visibleFields.length > 0 ? (
                            visibleFields.map((field) =>
                                ["address", "file", "repeatable_table"].includes(field.type) ? (
                                    <PreviewFallbackField key={field.key} field={field} />
                                ) : (
                                    <PublicFormFieldRenderer
                                        key={field.key}
                                        field={field}
                                        value={answers[field.key]}
                                        updateField={(fieldKey, value) =>
                                            setAnswers((prev) => ({ ...prev, [fieldKey]: value }))
                                        }
                                        datePickerOpen={datePickerOpen}
                                        setDatePickerOpen={setDatePickerOpen}
                                    />
                                ),
                            )
                        ) : (
                            <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
                                <p className="text-base font-semibold text-stone-900">Nothing to preview on this page yet</p>
                                <p className="mt-2 text-sm text-stone-500">
                                    Add fields in Edit to see the branded preview here.
                                </p>
                            </div>
                        )}
                    </div>

                    {privacyNotice ? (
                        <p className="mt-6 border-t border-stone-200/80 pt-4 text-xs text-stone-500">
                            {privacyNotice}
                        </p>
                    ) : null}
                </div>
            </div>
        </div>
    )
}
