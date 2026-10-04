"use client"

import * as React from "react"
import { CopyIcon, PlusIcon, Trash2Icon, XIcon } from "lucide-react"

import { FormBuilderFieldPreview } from "@/components/forms/FormBuilderFieldPreview"
import { FormBuilderPalette } from "@/components/forms/FormBuilderPalette"
import { PublicFormFieldRenderer } from "@/components/forms/PublicFormFieldRenderer"
import { DonorFieldSensitivitySelect } from "@/components/forms/builder/DonorFieldSensitivitySelect"
import { FieldLibraryDialog } from "@/components/forms/builder/FieldLibraryDialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { FormField, FormFieldValidation, FormLeadKind, FormSurrogateFieldOption } from "@/lib/api/forms"
import {
    getBuilderOptionLabel,
    getBuilderOptionValue,
    parseOptionalInt,
    parseOptionalNumber,
    updateBuilderOptionLabel,
    type BuilderFormField,
    type BuilderFormPage,
} from "@/lib/forms/form-builder-document"
import { getBuilderFieldTypeLabel, type BuilderPaletteField } from "@/lib/forms/form-builder-library"
import { cn } from "@/lib/utils"

type WorkspaceDocument = {
    pages: BuilderFormPage[]
    activePage: number
    currentPage: BuilderFormPage
    selectedField: string | null
    selectedFieldData: BuilderFormField | null
    dropIndicatorId: string | "end" | null
    isDragging: boolean
    setActivePage: (pageId: number) => void
    selectField: (fieldId: string | null) => void
    handleAddPage: () => void
    handleDuplicatePage: (pageId: number) => void
    handleRenamePage: (pageId: number, name: string) => void
    handleMovePage: (pageId: number, direction: "up" | "down") => void
    requestDeletePage: (pageId: number) => void
    handleDragStart: (field: BuilderPaletteField) => void
    handleFieldDragStart: (fieldId: string) => void
    handleDragOver: (e: React.DragEvent) => void
    handleCanvasDragOver: (e: React.DragEvent) => void
    handleFieldDragOver: (e: React.DragEvent, fieldId: string) => void
    handleDrop: (e: React.DragEvent) => void
    handleDropOnField: (e: React.DragEvent, fieldId: string) => void
    handleDragEnd: () => void
    handleInsertField: (field: BuilderPaletteField) => void
    handleUpdateField: (fieldId: string, updates: Partial<BuilderFormField>) => void
    handleDuplicateField: (fieldId: string) => void
    handleDeleteField: (fieldId: string) => void
    handleValidationChange: (fieldId: string, updates: Partial<FormFieldValidation>) => void
    handleAddColumn: (fieldId: string) => void
    handleUpdateColumn: (
        fieldId: string,
        columnId: string,
        updates: Partial<NonNullable<BuilderFormField["columns"]>[number]>,
    ) => void
    handleRemoveColumn: (fieldId: string, columnId: string) => void
    handleAddRow: (fieldId: string) => void
    handleUpdateRow: (
        fieldId: string,
        rowId: string,
        updates: Partial<NonNullable<BuilderFormField["rows"]>[number]>,
    ) => void
    handleRemoveRow: (fieldId: string, rowId: string) => void
    handleShowIfChange: (
        fieldId: string,
        updates: Partial<NonNullable<BuilderFormField["showIf"]>>,
    ) => void
    handleMappingChange: (fieldId: string, value: string | null) => void
    syncOptionKeys: (fieldId: string, optionCount: number) => string[]
    addOption: (fieldId: string) => void
    removeOption: (fieldId: string, optionIndex: number) => void
}

type FormBuilderWorkspaceProps = {
    leadKind: FormLeadKind
    desktopCanvasWidthClass: string
    canvasFrameClass: string
    mappingOptions: FormSurrogateFieldOption[]
    publicEyebrow: string
    publicTitle: string
    publicSubtitle: string
    fieldLibrarySearch: string
    fieldLibraryCategory: string
    onFieldLibrarySearchChange: (value: string) => void
    onFieldLibraryCategoryChange: (value: string) => void
    document: WorkspaceDocument
    /** Rendered at the top of the right settings panel, above field settings. */
    inspectorHeader?: React.ReactNode
}

function buildCanvasField(field: BuilderFormField): FormField {
    return {
        key: field.id,
        label: field.label,
        type: field.type,
        required: field.required,
        options: field.options?.map((option) => ({
            label: getBuilderOptionLabel(option),
            value: getBuilderOptionValue(option),
        })) ?? null,
        validation: field.validation ?? null,
        help_text: field.helperText || null,
        show_if: field.showIf
            ? {
                field_key: field.showIf.fieldKey,
                operator: field.showIf.operator,
                value: field.showIf.value ?? null,
            }
            : null,
        columns: field.columns?.map((column) => ({
            key: column.id,
            label: column.label,
            type: column.type,
            required: column.required,
            options: column.options?.map((option) => ({
                label: getBuilderOptionLabel(option), value: getBuilderOptionValue(option),
            })) ?? null,
            validation: column.validation ?? null,
        })) ?? null,
        rows: field.rows?.map((row) => ({
            key: row.id,
            label: row.label,
            help_text: row.helpText || null,
        })) ?? null,
        min_rows: field.minRows ?? null,
        max_rows: field.maxRows ?? null,
    }
}

const TABLE_COLUMN_TYPE_LABELS: Record<NonNullable<BuilderFormField["columns"]>[number]["type"], string> = {
    text: "Text",
    textarea: "Long text",
    number: "Number",
    date: "Date",
    select: "Select",
    radio: "Yes / No",
}

const SHOW_IF_OPERATOR_LABELS: Record<NonNullable<BuilderFormField["showIf"]>["operator"], string> = {
    equals: "Equals",
    not_equals: "Does not equal",
    contains: "Contains",
    not_contains: "Does not contain",
    is_empty: "Is empty",
    is_not_empty: "Is not empty",
}

function InspectorSection({
    title,
    children,
}: {
    title: string
    children: React.ReactNode
}) {
    return (
        <section className="space-y-3 border-b border-border/70 px-5 py-4 last:border-b-0">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
            {children}
        </section>
    )
}

function UnsupportedCanvasField({ field }: { field: BuilderFormField }) {
    const publicField = buildCanvasField(field)

    return (
        <div className="space-y-2 rounded-xl border border-neutral-200 bg-neutral-50 p-3.5">
            <Label className="text-sm font-medium">
                {publicField.label}
                {publicField.required ? <span className="text-red-500"> *</span> : null}
            </Label>
            <FormBuilderFieldPreview
                label={field.label}
                type={field.type}
                surrogateFieldMapping={field.surrogateFieldMapping}
                options={field.options}
                columns={field.columns}
                rows={field.rows}
            />
            {publicField.help_text ? <p className="text-xs text-neutral-500">{publicField.help_text}</p> : null}
        </div>
    )
}

function CanvasFieldSurface({
    field,
    selected,
    isDragging,
    showDropIndicator,
    onDragOver,
    onDrop,
    onDragStart,
    onDragEnd,
    onSelect,
    onDuplicate,
    onDelete,
    mappingLabel,
}: {
    mappingLabel: string | null
    field: BuilderFormField
    selected: boolean
    isDragging: boolean
    showDropIndicator: boolean
    onDragOver: (event: React.DragEvent, fieldId: string) => void
    onDrop: (event: React.DragEvent, fieldId: string) => void
    onDragStart: (fieldId: string) => void
    onDragEnd: () => void
    onSelect: (fieldId: string) => void
    onDuplicate: (fieldId: string) => void
    onDelete: (fieldId: string) => void
}) {
    const [datePickerOpen, setDatePickerOpen] = React.useState<Record<string, boolean>>({})
    const publicField = buildCanvasField(field)
    const fieldLabel = field.label.trim() || "Untitled"
    const usesFallbackRenderer = ["address", "file", "repeatable_table"].includes(field.type)
    const floatingActionButtonClass =
        "pointer-events-auto rounded-full border border-neutral-200/80 bg-white/95 text-neutral-700 shadow-sm backdrop-blur hover:border-primary/40 hover:bg-white hover:text-neutral-950"

    return (
        <div className="space-y-2">
            {isDragging && showDropIndicator ? <div className="h-1 rounded-full bg-primary" /> : null}
            <div
                className={cn(
                    "group relative rounded-lg border-2 transition-colors",
                    selected
                        ? "border-primary/70 bg-primary/5"
                        : "border-transparent hover:border-border",
                )}
            >
                <Button unstyled
                    type="button"
                    draggable
                    aria-label={`Select ${fieldLabel} field`}
                    onClick={() => onSelect(field.id)}
                    onDragStart={() => onDragStart(field.id)}
                    onDragOver={(event) => onDragOver(event, field.id)}
                    onDrop={(event) => onDrop(event, field.id)}
                    onDragEnd={onDragEnd}
                    className="absolute inset-0 z-0 rounded-[inherit] border-0 bg-transparent p-0 text-left text-inherit outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
                {selected ? (
                    <div
                        data-testid="form-builder-selected-field-actions"
                        className="pointer-events-none absolute right-4 top-4 z-20 flex items-center gap-1.5"
                    >
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className={floatingActionButtonClass}
                            onClick={(event) => {
                                event.stopPropagation()
                                onDuplicate(field.id)
                            }}
                            aria-label={`Duplicate ${fieldLabel}`}
                        >
                            <CopyIcon className="size-4" />
                        </Button>
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className={floatingActionButtonClass}
                            onClick={(event) => {
                                event.stopPropagation()
                                onDelete(field.id)
                            }}
                            aria-label={`Delete ${fieldLabel}`}
                        >
                            <XIcon className="size-4" />
                        </Button>
                    </div>
                ) : null}
                <div
                    data-testid={selected ? "form-builder-selected-field-body" : undefined}
                    className="pointer-events-none relative z-10 p-3.5 pt-3.5"
                >
                    <div className="relative">
                        {usesFallbackRenderer ? (
                            <UnsupportedCanvasField field={field} />
                        ) : (
                            <PublicFormFieldRenderer
                                field={publicField}
                                value={undefined}
                                updateField={() => undefined}
                                datePickerOpen={datePickerOpen}
                                setDatePickerOpen={setDatePickerOpen}
                            />
                        )}
                    </div>
                    {mappingLabel || field.showIf ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                            {mappingLabel ? (
                                <span className="inline-flex h-5 items-center rounded-full bg-muted px-2 text-[11px] text-muted-foreground">
                                    Mapped to {mappingLabel}
                                </span>
                            ) : null}
                            {field.showIf ? (
                                <span className="inline-flex h-5 items-center rounded-full bg-muted px-2 text-[11px] text-muted-foreground">
                                    Conditional
                                </span>
                            ) : null}
                        </div>
                    ) : null}
                </div>
            </div>
        </div>
    )
}

function PageList({
    pages,
    activePage,
    onSetActivePage,
    onAddPage,
}: {
    pages: BuilderFormPage[]
    activePage: number
    onSetActivePage: (pageId: number) => void
    onAddPage: () => void
}) {
    return (
        <div className="flex flex-col gap-1 p-3">
            <nav aria-label="Form pages" className="flex flex-col gap-0.5">
                {pages.map((page, index) => {
                    const pageLabel = page.name.trim() || `Page ${index + 1}`
                    const isActive = page.id === activePage

                    return (
                        <Button unstyled
                            key={page.id}
                            type="button"
                            aria-current={isActive ? "page" : undefined}
                            onClick={() => onSetActivePage(page.id)}
                            className={cn(
                                "flex h-9 items-center gap-2.5 rounded-md px-2.5 text-left text-sm transition-colors",
                                isActive
                                    ? "bg-primary/10 font-medium text-foreground"
                                    : "text-foreground hover:bg-muted",
                            )}
                        >
                            <span className="w-5 shrink-0 font-mono text-xs text-muted-foreground">
                                {String(index + 1).padStart(2, "0")}
                            </span>
                            <span className="min-w-0 flex-1 truncate">{pageLabel}</span>
                            <span className="shrink-0 text-xs text-muted-foreground">{page.fields.length}</span>
                        </Button>
                    )
                })}
            </nav>
            <Button type="button" variant="ghost" size="sm" className="justify-start" onClick={onAddPage}>
                <PlusIcon aria-hidden="true" />
                Add page
            </Button>
        </div>
    )
}

function WorkspaceRail({
    leadKind,
    pages,
    activePage,
    fieldLibrarySearch,
    fieldLibraryCategory,
    onFieldLibrarySearchChange,
    onFieldLibraryCategoryChange,
    onSetActivePage,
    onAddPage,
    onInsertField,
    onFieldDragStart,
    onFieldDragEnd,
}: {
    leadKind: FormLeadKind
    pages: BuilderFormPage[]
    activePage: number
    fieldLibrarySearch: string
    fieldLibraryCategory: string
    onFieldLibrarySearchChange: (value: string) => void
    onFieldLibraryCategoryChange: (value: string) => void
    onSetActivePage: (pageId: number) => void
    onAddPage: () => void
    onInsertField: (field: BuilderPaletteField) => void
    onFieldDragStart: (field: BuilderPaletteField) => void
    onFieldDragEnd: () => void
}) {
    const [tab, setTab] = React.useState("fields")

    return (
        <aside
            data-testid="form-builder-rail"
            aria-label="Fields and pages"
            className="flex h-[24rem] min-h-0 w-full shrink-0 flex-col border-b border-border bg-card lg:h-auto lg:border-r lg:border-b-0"
        >
            <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col gap-0">
                <div className="border-b border-border/70 px-3 py-2">
                    <TabsList aria-label="Builder library" className="grid w-full grid-cols-2">
                        <TabsTrigger value="fields">Fields</TabsTrigger>
                        <TabsTrigger value="pages">
                            Pages
                            <span className="text-xs text-muted-foreground">{pages.length}</span>
                        </TabsTrigger>
                    </TabsList>
                </div>
                <TabsContent value="fields" className="mt-0 flex min-h-0 flex-1 flex-col">
                    <FormBuilderPalette
                        leadKind={leadKind}
                        activeCategory={fieldLibraryCategory}
                        search={fieldLibrarySearch}
                        onCategoryChange={onFieldLibraryCategoryChange}
                        onSearchChange={onFieldLibrarySearchChange}
                        onInsertField={onInsertField}
                        onFieldDragStart={onFieldDragStart}
                        onFieldDragEnd={onFieldDragEnd}
                    />
                </TabsContent>
                <TabsContent value="pages" className="mt-0 min-h-0 flex-1 overflow-y-auto">
                    <PageList
                        pages={pages}
                        activePage={activePage}
                        onSetActivePage={onSetActivePage}
                        onAddPage={onAddPage}
                    />
                </TabsContent>
            </Tabs>
        </aside>
    )
}

function CanvasPageHeader({
    pages,
    activePage,
    currentPage,
    onRenamePage,
    onDuplicatePage,
    onRequestDeletePage,
}: {
    pages: BuilderFormPage[]
    activePage: number
    currentPage: BuilderFormPage
    onRenamePage: (pageId: number, name: string) => void
    onDuplicatePage: (pageId: number) => void
    onRequestDeletePage: (pageId: number) => void
}) {
    const activeIndex = Math.max(0, pages.findIndex((page) => page.id === activePage))
    const currentPageLabel = currentPage.name.trim() || `Page ${activeIndex + 1}`

    return (
        <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0 flex-1 basis-60 space-y-1">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Page {activeIndex + 1} of {pages.length}
                </p>
                <Input
                    aria-label="Edit page name"
                    value={currentPage.name}
                    placeholder={currentPageLabel}
                    onChange={(event) => onRenamePage(currentPage.id, event.target.value)}
                    className="h-auto rounded-sm border-0 bg-transparent p-0 text-xl font-semibold text-foreground shadow-none md:text-xl"
                />
            </div>
            <div className="flex items-center gap-1">
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onDuplicatePage(activePage)}
                    aria-label={`Duplicate ${currentPageLabel}`}
                >
                    <CopyIcon aria-hidden="true" />
                    Duplicate
                </Button>
                <Button
                    type="button"
                    variant="destructive-ghost"
                    size="sm"
                    onClick={() => onRequestDeletePage(activePage)}
                    disabled={pages.length === 1}
                    aria-label={`Delete page ${currentPageLabel}`}
                >
                    <Trash2Icon aria-hidden="true" />
                    Delete page
                </Button>
            </div>
        </div>
    )
}

function EditCanvas({
    desktopCanvasWidthClass,
    canvasFrameClass,
    publicEyebrow,
    publicTitle,
    publicSubtitle,
    pageHeader,
    onOpenFieldLibrary,
    currentPage,
    selectedField,
    isDragging,
    dropIndicatorId,
    onCanvasDragOver,
    onDrop,
    onFieldDragOver,
    onDropOnField,
    onFieldDragStart,
    onDragEnd,
    onSelectField,
    onDuplicateField,
    onDeleteField,
    mappingLabels,
}: {
    mappingLabels: Map<string, string>
    desktopCanvasWidthClass: string
    canvasFrameClass: string
    publicEyebrow: string
    publicTitle: string
    publicSubtitle: string
    pageHeader: React.ReactNode
    onOpenFieldLibrary: () => void
    currentPage: BuilderFormPage
    selectedField: string | null
    isDragging: boolean
    dropIndicatorId: string | "end" | null
    onCanvasDragOver: (event: React.DragEvent) => void
    onDrop: (event: React.DragEvent) => void
    onFieldDragOver: (event: React.DragEvent, fieldId: string) => void
    onDropOnField: (event: React.DragEvent, fieldId: string) => void
    onFieldDragStart: (fieldId: string) => void
    onDragEnd: () => void
    onSelectField: (fieldId: string) => void
    onDuplicateField: (fieldId: string) => void
    onDeleteField: (fieldId: string) => void
}) {
    const displayTitle = publicTitle.trim()
    const displayEyebrow = publicEyebrow.trim()
    const displaySubtitle = publicSubtitle.trim()

    return (
        <section data-testid="form-builder-canvas" className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-muted/30 p-4 sm:p-6 xl:p-8">
            <div className="mx-auto flex h-full min-h-full flex-col gap-4">
                <div className={cn("mx-auto w-full", desktopCanvasWidthClass)}>{pageHeader}</div>
                <div
                    onDragOver={onCanvasDragOver}
                    onDrop={onDrop}
                    className={cn("mx-auto w-full", desktopCanvasWidthClass)}
                >
                    <div data-testid="form-builder-page-shell" className={cn("space-y-6", canvasFrameClass)}>
                        <div className="space-y-1 border-b border-neutral-200/80 pb-4">
                            {displayEyebrow ? (
                                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-neutral-400">
                                    {displayEyebrow}
                                </p>
                            ) : null}
                            {displayTitle ? (
                                <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 md:text-[28px]">
                                    {displayTitle}
                                </h1>
                            ) : null}
                            {displaySubtitle ? (
                                <p className="max-w-2xl text-sm text-neutral-500">{displaySubtitle}</p>
                            ) : null}
                        </div>

                        <div className="space-y-2">
                            {currentPage.fields.length === 0 ? (
                                <div className="rounded-lg border border-dashed border-border p-8 text-center">
                                    <p className="text-sm font-medium text-foreground">Add fields to this page</p>
                                </div>
                            ) : (
                                <>
                                    {currentPage.fields.map((field) => (
                                        <CanvasFieldSurface
                                            key={field.id}
                                            field={field}
                                            selected={selectedField === field.id}
                                            isDragging={isDragging}
                                            showDropIndicator={dropIndicatorId === field.id}
                                            onDragOver={onFieldDragOver}
                                            onDrop={onDropOnField}
                                            onDragStart={onFieldDragStart}
                                            onDragEnd={onDragEnd}
                                            onSelect={onSelectField}
                                            onDuplicate={onDuplicateField}
                                            onDelete={onDeleteField}
                                            mappingLabel={
                                                field.surrogateFieldMapping
                                                    ? mappingLabels.get(field.surrogateFieldMapping) ?? field.surrogateFieldMapping
                                                    : null
                                            }
                                        />
                                    ))}
                                    {isDragging && dropIndicatorId === "end" ? <div className="h-1 rounded-full bg-primary" /> : null}
                                </>
                            )}
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="w-full justify-center border border-dashed border-border text-muted-foreground hover:text-foreground"
                                onClick={onOpenFieldLibrary}
                            >
                                <PlusIcon aria-hidden="true" />
                                Add field
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    )
}

const INSPECTOR_PANEL_CLASS =
    "w-full border-t border-border bg-card lg:min-h-0 lg:overflow-y-auto lg:border-t-0 lg:border-l"

function FieldInspectorHeader({
    field,
    onDuplicate,
    onDelete,
    onClose,
}: {
    field: BuilderFormField
    onDuplicate: (fieldId: string) => void
    onDelete: (fieldId: string) => void
    onClose: () => void
}) {
    const fieldLabel = field.label.trim() || "Untitled"

    return (
        <div className="sticky top-0 z-10 flex items-center gap-1 border-b border-border bg-card px-5 py-3">
            <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
                {getBuilderFieldTypeLabel(field.type)}
            </h2>
            <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => onDuplicate(field.id)}
                aria-label={`Duplicate ${fieldLabel} field`}
            >
                <CopyIcon aria-hidden="true" />
            </Button>
            <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => onDelete(field.id)}
                aria-label={`Delete ${fieldLabel} field`}
            >
                <Trash2Icon aria-hidden="true" />
            </Button>
            <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close field settings">
                <XIcon aria-hidden="true" />
            </Button>
        </div>
    )
}

function useFieldInspectorView({
    leadKind,
    currentPage,
    selectedFieldData,
    mappingOptions,
    onUpdateField,
    onValidationChange,
    onAddColumn,
    onUpdateColumn,
    onRemoveColumn,
    onAddRow,
    onUpdateRow,
    onRemoveRow,
    onShowIfChange,
    onMappingChange,
    syncOptionKeys,
    addOption,
    removeOption,
    onDuplicateField,
    onDeleteField,
    onClose,
    header,
}: {
    header?: React.ReactNode
    onDuplicateField: (fieldId: string) => void
    onDeleteField: (fieldId: string) => void
    onClose: () => void
    leadKind: FormLeadKind
    currentPage: BuilderFormPage
    selectedFieldData: BuilderFormField | null
    mappingOptions: FormSurrogateFieldOption[]
    onUpdateField: (fieldId: string, updates: Partial<BuilderFormField>) => void
    onValidationChange: (fieldId: string, updates: Partial<FormFieldValidation>) => void
    onAddColumn: (fieldId: string) => void
    onUpdateColumn: (
        fieldId: string,
        columnId: string,
        updates: Partial<NonNullable<BuilderFormField["columns"]>[number]>,
    ) => void
    onRemoveColumn: (fieldId: string, columnId: string) => void
    onAddRow: (fieldId: string) => void
    onUpdateRow: (
        fieldId: string,
        rowId: string,
        updates: Partial<NonNullable<BuilderFormField["rows"]>[number]>,
    ) => void
    onRemoveRow: (fieldId: string, rowId: string) => void
    onShowIfChange: (
        fieldId: string,
        updates: Partial<NonNullable<BuilderFormField["showIf"]>>,
    ) => void
    onMappingChange: (fieldId: string, value: string | null) => void
    syncOptionKeys: (fieldId: string, optionCount: number) => string[]
    addOption: (fieldId: string) => void
    removeOption: (fieldId: string, optionIndex: number) => void
}) {
    const selectedFieldId = selectedFieldData?.id ?? null
    const conditionalFields = currentPage.fields.filter((field) => field.id !== selectedFieldId)
    const fieldLabelMap = new Map(
        conditionalFields.map((field) => [field.id, field.label.trim() || "Untitled field"] as const),
    )
    const mappingLabelMap = new Map(mappingOptions.map((mapping) => [mapping.value, mapping.label] as const))

    if (!selectedFieldData) {
        // The drawer only opens for publish readiness when no field is selected.
        if (!header) return null
        return (
            <aside data-testid="form-builder-settings" aria-label="Field settings" className={INSPECTOR_PANEL_CLASS}>
                <div className="p-4">{header}</div>
            </aside>
        )
    }

    return (
        <aside data-testid="form-builder-settings" aria-label="Field settings" className={INSPECTOR_PANEL_CLASS}>
            <FieldInspectorHeader
                field={selectedFieldData}
                onDuplicate={onDuplicateField}
                onDelete={onDeleteField}
                onClose={onClose}
            />
            {header ? <div className="border-b border-border/70 p-4">{header}</div> : null}
            <div>
                        <InspectorSection title="Basics">
                            <div className="space-y-2">
                                <Label htmlFor="field-title">Field title</Label>
                                <Input
                                    id="field-title"
                                    aria-label="Field title"
                                    value={selectedFieldData.label}
                                    onChange={(event) => onUpdateField(selectedFieldData.id, { label: event.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="field-helper">Field description</Label>
                                <Textarea
                                    id="field-helper"
                                    value={selectedFieldData.helperText}
                                    onChange={(event) => onUpdateField(selectedFieldData.id, { helperText: event.target.value })}
                                    placeholder={selectedFieldData.type === "checkbox"
                                        ? "Add your consent wording and links: [Privacy Notice](https://your-website.com/privacy)"
                                        : "Optional hint for users"}
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-2xl border border-border/70 bg-muted/20 px-3 py-2">
                                <Label htmlFor="field-required">Required field</Label>
                                <Switch
                                    id="field-required"
                                    checked={selectedFieldData.required}
                                    onCheckedChange={(checked) => onUpdateField(selectedFieldData.id, { required: checked })}
                                />
                            </div>
                        </InspectorSection>

                        {selectedFieldData.options ? (
                            <InspectorSection title="Options">
                                <div className="space-y-2">
                                    {(() => {
                                        const optionKeys = syncOptionKeys(selectedFieldData.id, selectedFieldData.options.length)
                                        return selectedFieldData.options.map((option, index) => (
                                            <div key={optionKeys[index]} className="flex gap-2">
                                                <Input
                                                    value={getBuilderOptionLabel(option)}
                                                    onChange={(event) => {
                                                        const nextOptions = [...selectedFieldData.options!]
                                                        nextOptions[index] = updateBuilderOptionLabel(option, event.target.value)
                                                        onUpdateField(selectedFieldData.id, { options: nextOptions })
                                                    }}
                                                />
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => removeOption(selectedFieldData.id, index)}
                                                    aria-label={`Remove option ${getBuilderOptionLabel(option) || `Option ${index + 1}`}`}
                                                >
                                                    <XIcon className="size-4" />
                                                </Button>
                                            </div>
                                        ))
                                    })()}
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="w-full bg-transparent"
                                        onClick={() => addOption(selectedFieldData.id)}
                                    >
                                        <PlusIcon className="mr-2 size-4" />
                                        Add Option
                                    </Button>
                                </div>
                            </InspectorSection>
                        ) : null}

                        {selectedFieldData.type === "repeatable_table" || selectedFieldData.type === "table" ? (
                            <InspectorSection title="Table setup">
                                {selectedFieldData.type === "repeatable_table" ? (
                                    <div className="grid grid-cols-2 gap-2">
                                        <Input
                                            inputMode="numeric"
                                            placeholder="Min rows"
                                            value={selectedFieldData.minRows ?? ""}
                                            onChange={(event) =>
                                                onUpdateField(selectedFieldData.id, {
                                                    minRows: parseOptionalInt(event.target.value),
                                                })
                                            }
                                        />
                                        <Input
                                            inputMode="numeric"
                                            placeholder="Max rows"
                                            value={selectedFieldData.maxRows ?? ""}
                                            onChange={(event) =>
                                                onUpdateField(selectedFieldData.id, {
                                                    maxRows: parseOptionalInt(event.target.value),
                                                })
                                            }
                                        />
                                    </div>
                                ) : null}

                                {selectedFieldData.type === "table" ? (
                                    <div className="space-y-3">
                                        {(selectedFieldData.rows || []).map((row) => (
                                            <div key={row.id} className="rounded-2xl border border-border/70 bg-muted/20 p-3">
                                                <div className="flex items-center gap-2">
                                                    <Input
                                                        value={row.label}
                                                        onChange={(event) =>
                                                            onUpdateRow(selectedFieldData.id, row.id, {
                                                                label: event.target.value,
                                                            })
                                                        }
                                                        placeholder="Row label"
                                                    />
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => onRemoveRow(selectedFieldData.id, row.id)}
                                                        aria-label={`Remove row ${row.label || "row"}`}
                                                    >
                                                        <XIcon className="size-4" />
                                                    </Button>
                                                </div>
                                                <Input
                                                    className="mt-2"
                                                    value={row.helpText}
                                                    onChange={(event) =>
                                                        onUpdateRow(selectedFieldData.id, row.id, {
                                                            helpText: event.target.value,
                                                        })
                                                    }
                                                    placeholder="Optional row helper text"
                                                />
                                            </div>
                                        ))}
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            className="w-full bg-transparent"
                                            onClick={() => onAddRow(selectedFieldData.id)}
                                        >
                                            <PlusIcon className="mr-2 size-4" />
                                            Add Row
                                        </Button>
                                    </div>
                                ) : null}

                                <div className="space-y-3">
                                    {(selectedFieldData.columns || []).map((column) => (
                                        <div key={column.id} className="rounded-2xl border border-border/70 bg-muted/20 p-3">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Input
                                                    value={column.label}
                                                    onChange={(event) =>
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            label: event.target.value,
                                                        })
                                                    }
                                                    placeholder="Column label"
                                                />
                                                <Select
                                                    value={column.type}
                                                    onValueChange={(value) => {
                                                        const nextType =
                                                            (value ?? "text") as NonNullable<BuilderFormField["columns"]>[number]["type"]
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            type: nextType,
                                                            options:
                                                                nextType === "select"
                                                                    ? column.options || ["Option 1", "Option 2"]
                                                                    : nextType === "radio"
                                                                        ? column.options || ["No", "Yes"]
                                                                        : [],
                                                        })
                                                    }}
                                                >
                                                    <SelectTrigger className="w-[130px]">
                                                        <SelectValue>
                                                            {(value: string | null) =>
                                                                TABLE_COLUMN_TYPE_LABELS[
                                                                    (value as keyof typeof TABLE_COLUMN_TYPE_LABELS) ?? "text"
                                                                ] ?? value ?? "Text"
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="text">Text</SelectItem>
                                                        <SelectItem value="textarea">Long text</SelectItem>
                                                        <SelectItem value="number">Number</SelectItem>
                                                        <SelectItem value="date">Date</SelectItem>
                                                        <SelectItem value="select">Select</SelectItem>
                                                        <SelectItem value="radio">Yes / No</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                                <Switch
                                                    checked={column.required}
                                                    onCheckedChange={(checked) =>
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            required: checked,
                                                        })
                                                    }
                                                />
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => onRemoveColumn(selectedFieldData.id, column.id)}
                                                    aria-label={`Remove column ${column.label || "column"}`}
                                                >
                                                    <XIcon className="size-4" />
                                                </Button>
                                            </div>
                                            {column.type === "select" || column.type === "radio" ? (
                                                <div className="mt-2 space-y-2">
                                                    {(column.options || []).map((option, optionIndex) => (
                                                        <div key={optionIndex} className="flex gap-2">
                                                            <Input
                                                                aria-label={`Option ${optionIndex + 1} for ${column.label}`}
                                                                value={getBuilderOptionLabel(option)}
                                                                onChange={(event) => onUpdateColumn(selectedFieldData.id, column.id, {
                                                                    options: (column.options || []).map((item, index) => index === optionIndex ? updateBuilderOptionLabel(item, event.target.value) : item),
                                                                })}
                                                            />
                                                            <Button type="button" variant="ghost" size="icon"
                                                                aria-label={`Remove option ${optionIndex + 1} from ${column.label}`}
                                                                onClick={() => onUpdateColumn(selectedFieldData.id, column.id, {
                                                                    options: (column.options || []).filter((_, index) => index !== optionIndex),
                                                                })}>
                                                                <XIcon className="size-4" />
                                                            </Button>
                                                        </div>
                                                    ))}
                                                    <Button type="button" variant="outline" size="sm"
                                                        onClick={() => onUpdateColumn(selectedFieldData.id, column.id, {
                                                            options: [...(column.options || []), "New option"],
                                                        })}>Add option</Button>
                                                </div>
                                            ) : null}
                                        </div>
                                    ))}
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="w-full bg-transparent"
                                    onClick={() => onAddColumn(selectedFieldData.id)}
                                >
                                    <PlusIcon className="mr-2 size-4" />
                                    Add Column
                                </Button>
                            </InspectorSection>
                        ) : null}
                        <InspectorSection title="Display rule">
                            <Select
                                value={selectedFieldData.showIf?.fieldKey || "none"}
                                onValueChange={(value) =>
                                    onShowIfChange(selectedFieldData.id, {
                                        fieldKey: value && value !== "none" ? value : "",
                                    })
                                }
                            >
                                <SelectTrigger aria-label="Show when">
                                    <SelectValue placeholder="Show when...">
                                        {(value: string | null) =>
                                            value === "none"
                                                ? "Always show"
                                                : fieldLabelMap.get(value ?? "") ?? value ?? "Show when..."
                                        }
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">Always show</SelectItem>
                                    {conditionalFields.map((field) => (
                                        <SelectItem key={field.id} value={field.id}>
                                            {field.label || "Untitled field"}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {selectedFieldData.showIf ? (
                                <>
                                    <Select
                                        value={selectedFieldData.showIf.operator}
                                        onValueChange={(value) =>
                                            onShowIfChange(selectedFieldData.id, {
                                                operator: value as NonNullable<BuilderFormField["showIf"]>["operator"],
                                            })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue>
                                                {(value: string | null) =>
                                                    SHOW_IF_OPERATOR_LABELS[
                                                        (value as keyof typeof SHOW_IF_OPERATOR_LABELS) ?? "equals"
                                                    ] ?? value ?? "Equals"
                                                }
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="equals">Equals</SelectItem>
                                            <SelectItem value="not_equals">Does not equal</SelectItem>
                                            <SelectItem value="contains">Contains</SelectItem>
                                            <SelectItem value="not_contains">Does not contain</SelectItem>
                                            <SelectItem value="is_empty">Is empty</SelectItem>
                                            <SelectItem value="is_not_empty">Is not empty</SelectItem>
                                        </SelectContent>
                                    </Select>

                                    {!["is_empty", "is_not_empty"].includes(selectedFieldData.showIf.operator) ? (
                                        (() => {
                                            const sourceField = currentPage.fields.find(
                                                (field) => field.id === selectedFieldData.showIf?.fieldKey,
                                            )
                                            const sourceOptions = sourceField?.options ?? []
                                            if (sourceOptions.length > 0) {
                                                return (
                                                    <Select
                                                        value={selectedFieldData.showIf?.value || ""}
                                                        onValueChange={(value) =>
                                                            onShowIfChange(selectedFieldData.id, {
                                                                value: value ?? "",
                                                            })
                                                        }
                                                    >
                                                        <SelectTrigger>
                                                            <SelectValue placeholder="Value to match">
                                                                {(value: string | null) =>
                                                                    sourceOptions.find((option) => getBuilderOptionValue(option) === value)
                                                                        ? getBuilderOptionLabel(
                                                                            sourceOptions.find(
                                                                                (option) => getBuilderOptionValue(option) === value,
                                                                            )!,
                                                                        )
                                                                        : value ?? "Value to match"
                                                                }
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {sourceOptions.map((option) => (
                                                                <SelectItem
                                                                    key={getBuilderOptionValue(option)}
                                                                    value={getBuilderOptionValue(option)}
                                                                >
                                                                    {getBuilderOptionLabel(option)}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                )
                                            }
                                            return (
                                                <Input
                                                    value={selectedFieldData.showIf?.value || ""}
                                                    onChange={(event) =>
                                                        onShowIfChange(selectedFieldData.id, { value: event.target.value })
                                                    }
                                                    placeholder="Value to match"
                                                />
                                            )
                                        })()
                                    ) : null}
                                </>
                            ) : null}
                        </InspectorSection>

                        {["text", "textarea", "email", "phone", "address"].includes(selectedFieldData.type) ||
                        selectedFieldData.type === "number" ? (
                            <InspectorSection title="Validation">
                                {["text", "textarea", "email", "phone", "address"].includes(selectedFieldData.type) ? (
                                    <>
                                        <div className="grid grid-cols-2 gap-2">
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Min length"
                                                value={selectedFieldData.validation?.min_length ?? ""}
                                                onChange={(event) =>
                                                    onValidationChange(selectedFieldData.id, {
                                                        min_length: parseOptionalNumber(event.target.value),
                                                    })
                                                }
                                            />
                                            <Input
                                                inputMode="numeric"
                                                placeholder="Max length"
                                                value={selectedFieldData.validation?.max_length ?? ""}
                                                onChange={(event) =>
                                                    onValidationChange(selectedFieldData.id, {
                                                        max_length: parseOptionalNumber(event.target.value),
                                                    })
                                                }
                                            />
                                        </div>
                                        <Input
                                            placeholder="Regex pattern (optional)"
                                            value={selectedFieldData.validation?.pattern ?? ""}
                                            onChange={(event) =>
                                                onValidationChange(selectedFieldData.id, { pattern: event.target.value })
                                            }
                                        />
                                    </>
                                ) : null}

                                {selectedFieldData.type === "number" ? (
                                    <div className="grid grid-cols-2 gap-2">
                                        <Input
                                            inputMode="numeric"
                                            placeholder="Min value"
                                            value={selectedFieldData.validation?.min_value ?? ""}
                                            onChange={(event) =>
                                                onValidationChange(selectedFieldData.id, {
                                                    min_value: parseOptionalNumber(event.target.value),
                                                })
                                            }
                                        />
                                        <Input
                                            inputMode="numeric"
                                            placeholder="Max value"
                                            value={selectedFieldData.validation?.max_value ?? ""}
                                            onChange={(event) =>
                                                onValidationChange(selectedFieldData.id, {
                                                    max_value: parseOptionalNumber(event.target.value),
                                                })
                                            }
                                        />
                                    </div>
                                ) : null}
                            </InspectorSection>
                        ) : null}

                        <DonorFieldSensitivitySelect
                            field={selectedFieldData}
                            leadKind={leadKind}
                            onChange={(sensitivity) => onUpdateField(selectedFieldData.id, { sensitivity })}
                        />

                        <InspectorSection title="Mapping">
                            <Select
                                value={selectedFieldData.surrogateFieldMapping || "none"}
                                onValueChange={(value) => onMappingChange(selectedFieldData.id, value)}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select field">
                                        {(value: string | null) =>
                                            value === "none"
                                                ? "None"
                                                : mappingLabelMap.get(value ?? "") ?? value ?? "Select field"
                                        }
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">None</SelectItem>
                                    {mappingOptions.map((mapping) => (
                                        <SelectItem key={mapping.value} value={mapping.value}>
                                            {mapping.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </InspectorSection>
            </div>
        </aside>
    )
}

function FieldInspector(props: Parameters<typeof useFieldInspectorView>[0]) {
    return useFieldInspectorView(props)
}

export function FormBuilderWorkspace({
    leadKind,
    desktopCanvasWidthClass,
    canvasFrameClass,
    mappingOptions,
    publicEyebrow,
    publicTitle,
    publicSubtitle,
    fieldLibrarySearch,
    fieldLibraryCategory,
    onFieldLibrarySearchChange,
    onFieldLibraryCategoryChange,
    document,
    inspectorHeader,
}: FormBuilderWorkspaceProps) {
    const [fieldLibraryOpen, setFieldLibraryOpen] = React.useState(false)
    const mappingLabels = React.useMemo(
        () => new Map(mappingOptions.map((mapping) => [mapping.value, mapping.label] as const)),
        [mappingOptions],
    )
    const drawerOpen = Boolean(document.selectedFieldData || inspectorHeader)

    return (
        <div
            data-testid="form-builder-workspace"
            className={cn(
                "flex min-h-0 flex-1 flex-col overflow-y-auto lg:grid lg:overflow-hidden",
                drawerOpen
                    ? "lg:grid-cols-[17rem_minmax(0,1fr)_22rem]"
                    : "lg:grid-cols-[17rem_minmax(0,1fr)]",
            )}
        >
            <WorkspaceRail
                leadKind={leadKind}
                pages={document.pages}
                activePage={document.activePage}
                fieldLibrarySearch={fieldLibrarySearch}
                fieldLibraryCategory={fieldLibraryCategory}
                onFieldLibrarySearchChange={onFieldLibrarySearchChange}
                onFieldLibraryCategoryChange={onFieldLibraryCategoryChange}
                onSetActivePage={document.setActivePage}
                onAddPage={document.handleAddPage}
                onInsertField={document.handleInsertField}
                onFieldDragStart={document.handleDragStart}
                onFieldDragEnd={document.handleDragEnd}
            />

            <EditCanvas
                desktopCanvasWidthClass={desktopCanvasWidthClass}
                canvasFrameClass={canvasFrameClass}
                publicEyebrow={publicEyebrow}
                publicTitle={publicTitle}
                publicSubtitle={publicSubtitle}
                pageHeader={
                    <CanvasPageHeader
                        pages={document.pages}
                        activePage={document.activePage}
                        currentPage={document.currentPage}
                        onRenamePage={document.handleRenamePage}
                        onDuplicatePage={document.handleDuplicatePage}
                        onRequestDeletePage={document.requestDeletePage}
                    />
                }
                onOpenFieldLibrary={() => setFieldLibraryOpen(true)}
                mappingLabels={mappingLabels}
                currentPage={document.currentPage}
                selectedField={document.selectedField}
                isDragging={document.isDragging}
                dropIndicatorId={document.dropIndicatorId}
                onCanvasDragOver={document.handleCanvasDragOver}
                onDrop={document.handleDrop}
                onFieldDragOver={document.handleFieldDragOver}
                onDropOnField={document.handleDropOnField}
                onFieldDragStart={document.handleFieldDragStart}
                onDragEnd={document.handleDragEnd}
                onSelectField={document.selectField}
                onDuplicateField={document.handleDuplicateField}
                onDeleteField={document.handleDeleteField}
            />

            <FieldInspector
                header={inspectorHeader}
                leadKind={leadKind}
                currentPage={document.currentPage}
                selectedFieldData={document.selectedFieldData}
                mappingOptions={mappingOptions}
                onUpdateField={document.handleUpdateField}
                onValidationChange={document.handleValidationChange}
                onAddColumn={document.handleAddColumn}
                onUpdateColumn={document.handleUpdateColumn}
                onRemoveColumn={document.handleRemoveColumn}
                onAddRow={document.handleAddRow}
                onUpdateRow={document.handleUpdateRow}
                onRemoveRow={document.handleRemoveRow}
                onShowIfChange={document.handleShowIfChange}
                onMappingChange={document.handleMappingChange}
                syncOptionKeys={document.syncOptionKeys}
                addOption={document.addOption}
                removeOption={document.removeOption}
                onDuplicateField={document.handleDuplicateField}
                onDeleteField={document.handleDeleteField}
                onClose={() => document.selectField(null)}
            />

            <FieldLibraryDialog
                leadKind={leadKind}
                open={fieldLibraryOpen}
                activeCategory={fieldLibraryCategory}
                search={fieldLibrarySearch}
                onOpenChange={setFieldLibraryOpen}
                onCategoryChange={onFieldLibraryCategoryChange}
                onSearchChange={onFieldLibrarySearchChange}
                onInsertField={(field) => {
                    document.handleInsertField(field)
                    setFieldLibraryOpen(false)
                }}
            />
        </div>
    )
}
