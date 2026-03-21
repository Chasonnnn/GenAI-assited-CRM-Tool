"use client"

import * as React from "react"
import { CopyIcon, Layers2Icon, PlusIcon, Settings2Icon, Trash2Icon, XIcon } from "lucide-react"

import { FormBuilderFieldPreview } from "@/components/forms/FormBuilderFieldPreview"
import { FormBuilderPalette } from "@/components/forms/FormBuilderPalette"
import { PublicFormFieldRenderer } from "@/components/forms/PublicFormFieldRenderer"
import { FieldLibrarySheet } from "@/components/forms/builder/FieldLibrarySheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { FormField, FormFieldValidation, FormSurrogateFieldOption } from "@/lib/api/forms"
import {
    parseOptionalInt,
    parseOptionalNumber,
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
    desktopCanvasWidthClass: string
    canvasFrameClass: string
    mappingOptions: FormSurrogateFieldOption[]
    formName: string
    formDescription: string
    publicTitle: string
    fieldLibrarySearch: string
    fieldLibraryCategory: string
    onFieldLibrarySearchChange: (value: string) => void
    onFieldLibraryCategoryChange: (value: string) => void
    document: WorkspaceDocument
}

function buildCanvasField(field: BuilderFormField): FormField {
    return {
        key: field.id,
        label: field.label,
        type: field.type,
        required: field.required,
        options: field.options?.map((option) => ({ label: option, value: option })) ?? null,
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
            options: column.options?.map((option) => ({ label: option, value: option })) ?? null,
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
    description,
    children,
}: {
    title: string
    description?: string
    children: React.ReactNode
}) {
    return (
        <section className="space-y-3 rounded-2xl border border-border/70 bg-background p-4">
            <div className="space-y-1">
                <h4 className="text-sm font-semibold text-foreground">{title}</h4>
                {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
            </div>
            {children}
        </section>
    )
}

function UnsupportedCanvasField({ field }: { field: BuilderFormField }) {
    const publicField = buildCanvasField(field)

    return (
        <div className="space-y-2 rounded-xl border border-stone-200 bg-stone-50 p-3.5">
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
            {publicField.help_text ? <p className="text-xs text-stone-500">{publicField.help_text}</p> : null}
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
}: {
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
    const publicField = React.useMemo(() => buildCanvasField(field), [field])
    const fieldLabel = field.label.trim() || "Untitled"
    const usesFallbackRenderer = ["address", "file", "repeatable_table"].includes(field.type)
    const floatingActionButtonClass =
        "pointer-events-auto rounded-full border border-stone-200/80 bg-white/95 text-stone-700 shadow-sm backdrop-blur hover:border-primary/40 hover:bg-white hover:text-stone-950"

    return (
        <div className="space-y-2">
            {isDragging && showDropIndicator ? <div className="h-1 rounded-full bg-primary" /> : null}
            <div
                className={cn(
                    "group relative rounded-[24px] border border-stone-200 bg-white transition-all",
                    selected
                        ? "border-primary/60 ring-2 ring-primary/15"
                        : "hover:border-primary/30",
                )}
            >
                <div
                    role="button"
                    tabIndex={0}
                    draggable
                    aria-label={`Select ${fieldLabel} field`}
                    onClick={() => onSelect(field.id)}
                    onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            onSelect(field.id)
                        }
                    }}
                    onDragStart={() => onDragStart(field.id)}
                    onDragOver={(event) => onDragOver(event, field.id)}
                    onDrop={(event) => onDrop(event, field.id)}
                    onDragEnd={onDragEnd}
                    className="rounded-[inherit] outline-none"
                >
                    <div
                        data-testid={selected ? "form-builder-selected-field-body" : undefined}
                        className="p-3.5 pt-3.5"
                    >
                        <div className="relative">
                            {selected ? (
                                <div
                                    data-testid="form-builder-selected-field-actions"
                                    className="pointer-events-none absolute right-4 top-4 z-10 flex items-center gap-1.5"
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

                            <div className="pointer-events-none">
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
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function PageStrip({
    pages,
    activePage,
    currentPage,
    onSetActivePage,
    onAddPage,
    onDuplicatePage,
    onRenamePage,
    onRequestDeletePage,
    onOpenFieldLibrary,
}: {
    pages: BuilderFormPage[]
    activePage: number
    currentPage: BuilderFormPage
    onSetActivePage: (pageId: number) => void
    onAddPage: () => void
    onDuplicatePage: (pageId: number) => void
    onRenamePage: (pageId: number, name: string) => void
    onRequestDeletePage: (pageId: number) => void
    onOpenFieldLibrary: () => void
}) {
    const activeIndex = Math.max(0, pages.findIndex((page) => page.id === activePage))
    const currentPageLabel = currentPage.name.trim() || `Page ${activeIndex + 1}`
    const getPageLabel = React.useCallback(
        (page: BuilderFormPage, index: number) => page.name.trim() || `Page ${index + 1}`,
        [],
    )

    return (
        <div className="border-b border-border/70 pb-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-2">
                    <div role="tablist" aria-label="Form pages" className="flex flex-wrap items-center gap-1.5">
                        {pages.map((page, index) => {
                            const pageLabel = getPageLabel(page, index)
                            const isActive = page.id === activePage
                            const widthStyle = { width: `${Math.max(7, Math.min(pageLabel.length + 2, 22))}ch` }

                            if (isActive) {
                                return (
                                    <div
                                        key={page.id}
                                        role="tab"
                                        aria-selected="true"
                                        aria-label={pageLabel}
                                        className="rounded-full border border-border bg-background px-3 py-1 shadow-sm"
                                    >
                                        <Input
                                            aria-label="Edit page name"
                                            value={page.name}
                                            placeholder={pageLabel}
                                            onChange={(event) => onRenamePage(page.id, event.target.value)}
                                            onClick={(event) => event.stopPropagation()}
                                            style={widthStyle}
                                            className="h-auto border-0 bg-transparent p-0 text-sm font-medium text-foreground shadow-none focus-visible:ring-0"
                                        />
                                    </div>
                                )
                            }

                            return (
                                <button
                                    key={page.id}
                                    type="button"
                                    role="tab"
                                    aria-selected="false"
                                    aria-label={pageLabel}
                                    onClick={() => onSetActivePage(page.id)}
                                    className="rounded-full px-3 py-1 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                                >
                                    {pageLabel}
                                </button>
                            )
                        })}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        {currentPage.fields.length} {currentPage.fields.length === 1 ? "field" : "fields"} on this page
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <Button type="button" variant="outline" size="sm" className="xl:hidden" onClick={onOpenFieldLibrary}>
                        <PlusIcon className="mr-2 size-4" />
                        Browse Fields
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={onAddPage}>
                        <PlusIcon className="mr-2 size-4" />
                        Add Page
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => onDuplicatePage(activePage)}
                        aria-label={`Duplicate ${currentPageLabel}`}
                    >
                        <CopyIcon className="mr-2 size-4" />
                        Duplicate
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => onRequestDeletePage(activePage)}
                        disabled={pages.length === 1}
                        aria-label={`Delete ${currentPageLabel}`}
                    >
                        <Trash2Icon className="mr-2 size-4" />
                        Delete
                    </Button>
                </div>
            </div>
        </div>
    )
}

function EditCanvas({
    desktopCanvasWidthClass,
    canvasFrameClass,
    formName,
    formDescription,
    publicTitle,
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
}: {
    desktopCanvasWidthClass: string
    canvasFrameClass: string
    formName: string
    formDescription: string
    publicTitle: string
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
    const displayTitle = publicTitle.trim() || formName.trim() || "Untitled form"

    return (
        <section data-testid="form-builder-canvas" className="min-h-0 min-w-0 overflow-y-auto bg-muted/20 p-4 sm:p-6 xl:p-8">
            <div className="mx-auto flex h-full min-h-full flex-col gap-4">
                <div
                    onDragOver={onCanvasDragOver}
                    onDrop={onDrop}
                    className={cn("mx-auto w-full", desktopCanvasWidthClass)}
                >
                    <div data-testid="form-builder-page-shell" className={cn("min-h-[58rem] space-y-6", canvasFrameClass)}>
                        <div className="space-y-1 border-b border-stone-200/80 pb-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">
                                {currentPage.name || "Current page"}
                            </p>
                            <h1 className="text-2xl font-semibold tracking-tight text-stone-900 md:text-[28px]">
                                {displayTitle}
                            </h1>
                            {formDescription.trim() ? (
                                <p className="max-w-2xl text-sm text-stone-500">{formDescription.trim()}</p>
                            ) : null}
                        </div>

                        <div className="space-y-4">
                            {currentPage.fields.length === 0 ? (
                                <div className="rounded-[24px] border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
                                    <p className="text-base font-semibold text-stone-900">Add fields to this page</p>
                                    <p className="mt-1.5 text-sm text-stone-500">
                                        Use the field browser to start this page.
                                    </p>
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
                                        />
                                    ))}
                                    {isDragging && dropIndicatorId === "end" ? <div className="h-1 rounded-full bg-primary" /> : null}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </section>
    )
}

function FieldInspector({
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
}: {
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
    const [activeTab, setActiveTab] = React.useState("general")
    const settingsPanelClass =
        "w-full border-t border-border/70 bg-card p-4 xl:min-h-[58rem] xl:w-auto xl:self-stretch xl:overflow-y-auto xl:border-t-0 xl:border-l xl:p-6"
    const selectedFieldId = selectedFieldData?.id ?? null
    const conditionalFields = React.useMemo(
        () => currentPage.fields.filter((field) => field.id !== selectedFieldId),
        [currentPage.fields, selectedFieldId],
    )
    const fieldLabelMap = React.useMemo(
        () =>
            new Map(
                conditionalFields.map((field) => [field.id, field.label.trim() || "Untitled field"] as const),
            ),
        [conditionalFields],
    )
    const mappingLabelMap = React.useMemo(
        () => new Map(mappingOptions.map((mapping) => [mapping.value, mapping.label] as const)),
        [mappingOptions],
    )

    React.useEffect(() => {
        setActiveTab("general")
    }, [selectedFieldData?.id])

    if (!selectedFieldData) {
        return (
            <aside data-testid="form-builder-settings" aria-label="Form builder settings" className={settingsPanelClass}>
                <div className="flex min-h-full flex-col gap-4">
                    <div className="rounded-2xl border border-border/70 bg-background p-4">
                        <div className="flex items-start gap-3">
                            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                <Layers2Icon className="size-5" />
                            </div>
                            <div className="min-w-0 flex-1 space-y-1">
                                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                    Current page
                                </p>
                                <h3 className="text-base font-semibold text-foreground">
                                    {currentPage.name || "Current page"}
                                </h3>
                                <p className="text-sm text-muted-foreground">
                                    {currentPage.fields.length} {currentPage.fields.length === 1 ? "field" : "fields"} on this page.
                                </p>
                            </div>
                        </div>
                    </div>

                    <InspectorSection title="Edit guidance" description="Select a field to edit it.">
                        <p className="text-sm text-muted-foreground">
                            The canvas shows the live form layout. Field details appear here when selected.
                        </p>
                    </InspectorSection>
                </div>
            </aside>
        )
    }

    return (
        <aside data-testid="form-builder-settings" aria-label="Form builder settings" className={settingsPanelClass}>
            <div className="flex min-h-full flex-col gap-4">
                <div className="rounded-2xl border border-border/70 bg-background p-4">
                    <div className="flex items-start gap-3">
                        <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                            <Settings2Icon className="size-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                Selected field
                            </p>
                            <h3 className="mt-1 truncate text-base font-semibold text-foreground">
                                {selectedFieldData.label || "Untitled field"}
                            </h3>
                            <div className="mt-2 flex flex-wrap gap-2">
                                <Badge variant="outline">{getBuilderFieldTypeLabel(selectedFieldData.type)}</Badge>
                                {selectedFieldData.required ? <Badge variant="secondary">Required</Badge> : null}
                                {selectedFieldData.surrogateFieldMapping ? <Badge variant="secondary">Mapped</Badge> : null}
                                {selectedFieldData.showIf ? <Badge variant="secondary">Conditional</Badge> : null}
                            </div>
                        </div>
                    </div>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex min-h-0 flex-1 flex-col gap-4">
                    <TabsList aria-label="Field settings sections" className="grid w-full grid-cols-2 bg-stone-100">
                        <TabsTrigger value="general">General</TabsTrigger>
                        <TabsTrigger value="advanced">Advanced</TabsTrigger>
                    </TabsList>

                    <TabsContent value="general" className="mt-0 space-y-4">
                        <InspectorSection title="Basics" description="Core copy and visibility for this field.">
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
                                <Input
                                    id="field-helper"
                                    value={selectedFieldData.helperText}
                                    onChange={(event) => onUpdateField(selectedFieldData.id, { helperText: event.target.value })}
                                    placeholder="Optional hint for users"
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
                            <InspectorSection title="Options" description="Manage the answer choices shown to applicants.">
                                <div className="space-y-2">
                                    {(() => {
                                        const optionKeys = syncOptionKeys(selectedFieldData.id, selectedFieldData.options.length)
                                        return selectedFieldData.options.map((option, index) => (
                                            <div key={optionKeys[index]} className="flex gap-2">
                                                <Input
                                                    value={option}
                                                    onChange={(event) => {
                                                        const nextOptions = [...selectedFieldData.options!]
                                                        nextOptions[index] = event.target.value
                                                        onUpdateField(selectedFieldData.id, { options: nextOptions })
                                                    }}
                                                />
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => removeOption(selectedFieldData.id, index)}
                                                    aria-label={`Remove option ${option || `Option ${index + 1}`}`}
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
                            <InspectorSection
                                title="Table setup"
                                description={
                                    selectedFieldData.type === "table"
                                        ? "Define fixed rows and the columns each row should capture."
                                        : "Define rows and columns for repeatable table capture."
                                }
                            >
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
                                            <div className="flex items-center gap-2">
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
                                                <Input
                                                    className="mt-2"
                                                    value={(column.options || []).join(", ")}
                                                    onChange={(event) =>
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            options: event.target.value
                                                                .split(",")
                                                                .map((entry) => entry.trim())
                                                                .filter(Boolean),
                                                        })
                                                    }
                                                    placeholder="Options (comma separated)"
                                                />
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
                    </TabsContent>

                    <TabsContent value="advanced" className="mt-0 space-y-4">
                        <InspectorSection title="Logic" description="Show or hide this field based on earlier answers.">
                            <div className="flex items-center justify-between">
                                <Label>Display Rules</Label>
                                {selectedFieldData.showIf ? (
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => onUpdateField(selectedFieldData.id, { showIf: null })}
                                    >
                                        Clear rule
                                    </Button>
                                ) : null}
                            </div>
                            <Select
                                value={selectedFieldData.showIf?.fieldKey || "none"}
                                onValueChange={(value) =>
                                    onShowIfChange(selectedFieldData.id, {
                                        fieldKey: value && value !== "none" ? value : "",
                                    })
                                }
                            >
                                <SelectTrigger>
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
                                                            <SelectValue placeholder="Value to match" />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {sourceOptions.map((option) => (
                                                                <SelectItem key={option} value={option}>
                                                                    {option}
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
                            <InspectorSection title="Validation" description="Apply limits and patterns for answer quality.">
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

                        <InspectorSection title="Mapping" description="Connect this field to a surrogate record field.">
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
                    </TabsContent>
                </Tabs>
            </div>
        </aside>
    )
}

export function FormBuilderWorkspace({
    desktopCanvasWidthClass,
    canvasFrameClass,
    mappingOptions,
    formName,
    formDescription,
    publicTitle,
    fieldLibrarySearch,
    fieldLibraryCategory,
    onFieldLibrarySearchChange,
    onFieldLibraryCategoryChange,
    document,
}: FormBuilderWorkspaceProps) {
    const [fieldLibraryOpen, setFieldLibraryOpen] = React.useState(false)

    return (
        <div
            data-testid="form-builder-workspace"
            className="flex min-h-0 flex-1 flex-col overflow-y-auto xl:grid xl:grid-cols-[clamp(21rem,32vw,31rem)_minmax(0,1fr)] xl:overflow-hidden"
        >
            <FormBuilderPalette
                className="hidden xl:block"
                activeCategory={fieldLibraryCategory}
                search={fieldLibrarySearch}
                onCategoryChange={onFieldLibraryCategoryChange}
                onSearchChange={onFieldLibrarySearchChange}
                onInsertField={document.handleInsertField}
                onFieldDragStart={document.handleDragStart}
                onFieldDragEnd={document.handleDragEnd}
            />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                <div className="border-b border-border/70 bg-background/95 p-4 supports-[backdrop-filter]:bg-background/60 sm:p-6 xl:p-6 xl:pb-3">
                    <PageStrip
                        pages={document.pages}
                        activePage={document.activePage}
                        currentPage={document.currentPage}
                        onSetActivePage={document.setActivePage}
                        onAddPage={document.handleAddPage}
                        onDuplicatePage={document.handleDuplicatePage}
                        onRenamePage={document.handleRenamePage}
                        onRequestDeletePage={document.requestDeletePage}
                        onOpenFieldLibrary={() => setFieldLibraryOpen(true)}
                    />
                </div>

                <div className="flex min-h-0 flex-1 flex-col xl:grid xl:grid-cols-[minmax(0,1fr)_clamp(18rem,23vw,24rem)] xl:items-stretch">
                    <EditCanvas
                        desktopCanvasWidthClass={desktopCanvasWidthClass}
                        canvasFrameClass={canvasFrameClass}
                        formName={formName}
                        formDescription={formDescription}
                        publicTitle={publicTitle}
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
                    />
                </div>
            </div>

            <FieldLibrarySheet
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
