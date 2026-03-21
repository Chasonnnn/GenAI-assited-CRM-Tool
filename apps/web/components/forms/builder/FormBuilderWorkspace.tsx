"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FormBuilderFieldPreview } from "@/components/forms/FormBuilderFieldPreview"
import { FieldLibrarySheet } from "@/components/forms/builder/FieldLibrarySheet"
import { FormBuilderCanvasPreview } from "@/components/forms/builder/FormBuilderCanvasPreview"
import {
    getBuilderFieldIcon,
    getBuilderFieldTypeLabel,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import {
    parseOptionalInt,
    parseOptionalNumber,
    type BuilderFormField,
    type BuilderFormPage,
} from "@/lib/forms/form-builder-document"
import type { FormFieldValidation, FormSurrogateFieldOption } from "@/lib/api/forms"
import { cn } from "@/lib/utils"
import {
    ArrowDownIcon,
    ArrowUpIcon,
    CopyIcon,
    EyeIcon,
    GripVerticalIcon,
    Layers2Icon,
    MonitorIcon,
    PlusIcon,
    Settings2Icon,
    SparklesIcon,
    Trash2Icon,
    XIcon,
} from "lucide-react"

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
    mobileCanvasWidthClass: string
    canvasFrameClass: string
    mappingOptions: FormSurrogateFieldOption[]
    formName: string
    formDescription: string
    publicTitle: string
    resolvedLogoUrl: string
    privacyNotice: string
    canvasMode: "compose" | "preview"
    previewDevice: "desktop" | "mobile"
    fieldLibraryOpen: boolean
    fieldLibrarySearch: string
    fieldLibraryCategory: string
    onCanvasModeChange: (value: "compose" | "preview") => void
    onPreviewDeviceChange: (value: "desktop" | "mobile") => void
    onFieldLibraryOpenChange: (open: boolean) => void
    onFieldLibrarySearchChange: (value: string) => void
    onFieldLibraryCategoryChange: (value: string) => void
    document: WorkspaceDocument
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
        <section className="space-y-3 rounded-[24px] border border-border/70 bg-background/95 p-4 shadow-sm">
            <div className="space-y-1">
                <h4 className="text-sm font-semibold text-foreground">{title}</h4>
                {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
            </div>
            {children}
        </section>
    )
}

function PageRail({
    pages,
    activePage,
    onSetActivePage,
    onAddPage,
    onDuplicatePage,
    onRenamePage,
    onMovePage,
    onRequestDeletePage,
    onOpenFieldLibrary,
}: {
    pages: BuilderFormPage[]
    activePage: number
    onSetActivePage: (pageId: number) => void
    onAddPage: () => void
    onDuplicatePage: (pageId: number) => void
    onRenamePage: (pageId: number, name: string) => void
    onMovePage: (pageId: number, direction: "up" | "down") => void
    onRequestDeletePage: (pageId: number) => void
    onOpenFieldLibrary: () => void
}) {
    return (
        <aside
            data-testid="form-builder-page-rail"
            className="space-y-4 rounded-[28px] border border-border/70 bg-card p-4 shadow-sm xl:rounded-none xl:border-0 xl:border-r xl:bg-card/90 xl:p-6 xl:shadow-none"
        >
            <div className="rounded-[24px] border border-border/70 bg-gradient-to-b from-sky-50 to-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-700/70">Builder flow</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">Pages</h3>
                <p className="mt-2 text-sm text-slate-600">
                    Organize multi-page forms, then open the field library for the active page.
                </p>
                <Button className="mt-4 w-full" onClick={onOpenFieldLibrary}>
                    <SparklesIcon className="mr-2 size-4" />
                    Add Fields
                </Button>
            </div>

            <div className="space-y-3">
                {pages.map((page, index) => {
                    const isActive = page.id === activePage
                    const pageLabel = page.name.trim() || `Page ${index + 1}`

                    return (
                        <div
                            key={page.id}
                            className={cn(
                                "rounded-[24px] border p-3 transition-all",
                                isActive
                                    ? "border-sky-200 bg-sky-50/70 shadow-sm"
                                    : "border-border/70 bg-background/80 hover:border-sky-200/70",
                            )}
                        >
                            <button
                                type="button"
                                aria-label={`Select page ${pageLabel}`}
                                onClick={() => onSetActivePage(page.id)}
                                className="flex w-full items-start justify-between gap-3 text-left"
                            >
                                <div>
                                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                        Page {index + 1}
                                    </p>
                                    <p className="mt-1 text-base font-semibold text-foreground">{pageLabel}</p>
                                </div>
                                <Badge variant={isActive ? "default" : "outline"}>
                                    {page.fields.length} {page.fields.length === 1 ? "field" : "fields"}
                                </Badge>
                            </button>

                            {isActive ? (
                                <div className="mt-4 space-y-3 border-t border-sky-200/70 pt-4">
                                    <div className="space-y-2">
                                        <Label htmlFor={`page-name-${page.id}`}>Page name</Label>
                                        <Input
                                            id={`page-name-${page.id}`}
                                            aria-label={`${pageLabel} name`}
                                            value={page.name}
                                            onChange={(event) => onRenamePage(page.id, event.target.value)}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => onMovePage(page.id, "up")}
                                            disabled={index === 0}
                                            aria-label={`Move ${pageLabel} up`}
                                        >
                                            <ArrowUpIcon className="mr-2 size-4" />
                                            Up
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => onMovePage(page.id, "down")}
                                            disabled={index === pages.length - 1}
                                            aria-label={`Move ${pageLabel} down`}
                                        >
                                            <ArrowDownIcon className="mr-2 size-4" />
                                            Down
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => onDuplicatePage(page.id)}
                                        >
                                            <CopyIcon className="mr-2 size-4" />
                                            Duplicate
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            className="text-destructive hover:text-destructive"
                                            onClick={() => onRequestDeletePage(page.id)}
                                            disabled={pages.length === 1}
                                        >
                                            <Trash2Icon className="mr-2 size-4" />
                                            Delete
                                        </Button>
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    )
                })}
            </div>

            <Button variant="outline" className="w-full bg-transparent" onClick={onAddPage}>
                <PlusIcon className="mr-2 size-4" />
                Add Page
            </Button>
        </aside>
    )
}

function ComposeCanvas({
    desktopCanvasWidthClass,
    canvasFrameClass,
    currentPage,
    selectedField,
    isDragging,
    dropIndicatorId,
    onDragOver,
    onCanvasDragOver,
    onDrop,
    onFieldDragStart,
    onFieldDragOver,
    onDropOnField,
    onDragEnd,
    onSelectField,
    onDuplicateField,
    onDeleteField,
    onOpenFieldLibrary,
}: {
    desktopCanvasWidthClass: string
    canvasFrameClass: string
    currentPage: BuilderFormPage
    selectedField: string | null
    isDragging: boolean
    dropIndicatorId: string | "end" | null
    onDragOver: (e: React.DragEvent) => void
    onCanvasDragOver: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
    onFieldDragStart: (fieldId: string) => void
    onFieldDragOver: (e: React.DragEvent, fieldId: string) => void
    onDropOnField: (e: React.DragEvent, fieldId: string) => void
    onDragEnd: () => void
    onSelectField: (fieldId: string) => void
    onDuplicateField: (fieldId: string) => void
    onDeleteField: (fieldId: string) => void
    onOpenFieldLibrary: () => void
}) {
    return (
        <div
            onDragOver={onCanvasDragOver}
            onDrop={onDrop}
            className={cn("mx-auto w-full space-y-4", desktopCanvasWidthClass, canvasFrameClass)}
        >
            {currentPage.fields.length === 0 ? (
                <div
                    onDragOver={onDragOver}
                    onDrop={onDrop}
                    className="flex min-h-[420px] flex-col items-center justify-center rounded-[28px] border-2 border-dashed border-border/80 bg-muted/10 p-8 text-center"
                >
                    <div className="flex size-20 items-center justify-center rounded-full bg-sky-100 text-sky-700">
                        <SparklesIcon className="size-9" />
                    </div>
                    <h3 className="mt-5 text-2xl font-semibold tracking-tight text-foreground">
                        Start with a field library
                    </h3>
                    <p className="mt-2 max-w-md text-sm text-muted-foreground">
                        Add recommended intake fields or custom controls to shape the active page.
                    </p>
                    <Button className="mt-5" onClick={onOpenFieldLibrary}>
                        <PlusIcon className="mr-2 size-4" />
                        Open field library
                    </Button>
                </div>
            ) : (
                <>
                    {currentPage.fields.map((field) => {
                        const Icon = getBuilderFieldIcon(field.type)
                        const fieldLabel = field.label || "Untitled field"

                        return (
                            <div key={field.id} className="space-y-2">
                                {isDragging && dropIndicatorId === field.id ? (
                                    <div className="h-1 rounded-full bg-primary" />
                                ) : null}
                                <div
                                    role="button"
                                    tabIndex={0}
                                    draggable
                                    aria-label={`${fieldLabel} field`}
                                    onClick={() => onSelectField(field.id)}
                                    onKeyDown={(event) => {
                                        if (event.key === "Enter" || event.key === " ") {
                                            event.preventDefault()
                                            onSelectField(field.id)
                                        }
                                    }}
                                    onDragStart={() => onFieldDragStart(field.id)}
                                    onDragOver={(event) => onFieldDragOver(event, field.id)}
                                    onDrop={(event) => onDropOnField(event, field.id)}
                                    onDragEnd={onDragEnd}
                                    className={cn(
                                        "rounded-[28px] border bg-background p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md",
                                        selectedField === field.id && "border-primary/40 ring-2 ring-primary/15",
                                    )}
                                >
                                    <div className="flex items-start gap-4">
                                        <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                            <Icon className="size-5" aria-hidden="true" />
                                        </div>

                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <h3 className="text-lg font-semibold text-foreground">{fieldLabel}</h3>
                                                <Badge variant="outline">{getBuilderFieldTypeLabel(field.type)}</Badge>
                                                {field.required ? <Badge variant="secondary">Required</Badge> : null}
                                                {field.surrogateFieldMapping ? <Badge variant="secondary">Mapped</Badge> : null}
                                                {field.showIf ? <Badge variant="secondary">Conditional</Badge> : null}
                                            </div>
                                            {field.helperText ? (
                                                <p className="mt-2 text-sm text-muted-foreground">{field.helperText}</p>
                                            ) : null}
                                            <div className="mt-4">
                                                <FormBuilderFieldPreview
                                                    label={field.label}
                                                    type={field.type}
                                                    surrogateFieldMapping={field.surrogateFieldMapping}
                                                    options={field.options}
                                                    columns={field.columns}
                                                />
                                            </div>
                                        </div>

                                        <GripVerticalIcon className="mt-1 size-5 text-muted-foreground/70" aria-hidden="true" />

                                        <div className="flex items-center gap-1">
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                onClick={(event) => {
                                                    event.stopPropagation()
                                                    onDuplicateField(field.id)
                                                }}
                                                aria-label={`Duplicate ${fieldLabel}`}
                                            >
                                                <CopyIcon className="size-4" />
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                onClick={(event) => {
                                                    event.stopPropagation()
                                                    onDeleteField(field.id)
                                                }}
                                                aria-label={`Delete ${fieldLabel}`}
                                            >
                                                <XIcon className="size-4" />
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )
                    })}

                    {isDragging && dropIndicatorId === "end" ? <div className="h-1 rounded-full bg-primary" /> : null}
                </>
            )}
        </div>
    )
}

function FieldInspector({
    canvasMode,
    currentPage,
    selectedFieldData,
    mappingOptions,
    onUpdateField,
    onValidationChange,
    onAddColumn,
    onUpdateColumn,
    onRemoveColumn,
    onShowIfChange,
    onMappingChange,
    syncOptionKeys,
    addOption,
    removeOption,
}: {
    canvasMode: "compose" | "preview"
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
    onShowIfChange: (
        fieldId: string,
        updates: Partial<NonNullable<BuilderFormField["showIf"]>>,
    ) => void
    onMappingChange: (fieldId: string, value: string | null) => void
    syncOptionKeys: (fieldId: string, optionCount: number) => string[]
    addOption: (fieldId: string) => void
    removeOption: (fieldId: string, optionIndex: number) => void
}) {
    return (
        <aside
            data-testid="form-builder-settings"
            aria-label="Form builder settings"
            className="w-full rounded-[28px] border border-border/70 bg-card p-4 shadow-sm xl:rounded-none xl:border-0 xl:border-l xl:bg-card/90 xl:p-6 xl:shadow-none"
        >
            {canvasMode === "preview" ? (
                <div className="rounded-[24px] border border-border/70 bg-muted/20 p-5">
                    <div className="flex items-center gap-3">
                        <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                            <EyeIcon className="size-5" />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold">Preview mode</h3>
                            <p className="text-xs text-muted-foreground">
                                Interact with the branded preview without changing saved builder data.
                            </p>
                        </div>
                    </div>
                </div>
            ) : selectedFieldData ? (
                <div className="space-y-4">
                    <div className="rounded-[24px] border border-border/70 bg-gradient-to-b from-slate-50 to-white p-4 shadow-sm">
                        <div className="flex items-start gap-3">
                            <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                <Settings2Icon className="size-5" />
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                    Field summary
                                </p>
                                <h3 className="mt-1 truncate text-lg font-semibold text-foreground">
                                    {selectedFieldData.label || "Untitled field"}
                                </h3>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    <Badge variant="outline">{getBuilderFieldTypeLabel(selectedFieldData.type)}</Badge>
                                    {selectedFieldData.required ? <Badge variant="secondary">Required</Badge> : null}
                                    {selectedFieldData.surrogateFieldMapping ? <Badge variant="secondary">Mapped</Badge> : null}
                                    {selectedFieldData.showIf ? <Badge variant="secondary">Conditional</Badge> : null}
                                </div>
                            </div>
                        </div>
                    </div>

                    <InspectorSection title="Basics" description="Core copy and visibility for this field.">
                        <div className="space-y-2">
                            <Label htmlFor="field-label">Label</Label>
                            <Input
                                id="field-label"
                                value={selectedFieldData.label}
                                onChange={(event) => onUpdateField(selectedFieldData.id, { label: event.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="field-helper">Helper Text</Label>
                            <Input
                                id="field-helper"
                                value={selectedFieldData.helperText}
                                onChange={(event) => onUpdateField(selectedFieldData.id, { helperText: event.target.value })}
                                placeholder="Optional hint for users"
                            />
                        </div>
                        <div className="flex items-center justify-between rounded-2xl border border-border/70 bg-muted/20 px-3 py-2">
                            <Label htmlFor="field-required">Required</Label>
                            <Switch
                                id="field-required"
                                checked={selectedFieldData.required}
                                onCheckedChange={(checked) => onUpdateField(selectedFieldData.id, { required: checked })}
                            />
                        </div>
                    </InspectorSection>

                    {selectedFieldData.options ? (
                        <InspectorSection
                            title="Options"
                            description="Manage the answer choices shown to applicants."
                        >
                            <div className="space-y-2">
                                {(() => {
                                    const optionKeys = syncOptionKeys(selectedFieldData.id, selectedFieldData.options.length)
                                    return selectedFieldData.options.map((option, index) => (
                                        <div key={optionKeys[index]} className="flex gap-2">
                                            <Input
                                                value={option}
                                                onChange={(event) => {
                                                    const newOptions = [...selectedFieldData.options!]
                                                    newOptions[index] = event.target.value
                                                    onUpdateField(selectedFieldData.id, { options: newOptions })
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

                    {selectedFieldData.type === "repeatable_table" ? (
                        <InspectorSection
                            title="Table setup"
                            description="Define rows and columns for repeatable table capture."
                        >
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
                                                    const nextType = (value ?? "text") as "text" | "number" | "date" | "select"
                                                    onUpdateColumn(selectedFieldData.id, column.id, {
                                                        type: nextType,
                                                        options: nextType === "select" ? column.options || ["Option 1", "Option 2"] : [],
                                                    })
                                                }}
                                            >
                                                <SelectTrigger className="w-[130px]">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="text">Text</SelectItem>
                                                    <SelectItem value="number">Number</SelectItem>
                                                    <SelectItem value="date">Date</SelectItem>
                                                    <SelectItem value="select">Select</SelectItem>
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
                                        {column.type === "select" ? (
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
                                <SelectValue placeholder="Show when..." />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">Always show</SelectItem>
                                {currentPage.fields
                                    .filter((field) => field.id !== selectedFieldData.id)
                                    .map((field) => (
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
                                        <SelectValue />
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
                                <SelectValue placeholder="Select field" />
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
            ) : (
                <div className="rounded-[24px] border border-border/70 bg-muted/20 p-5">
                    <div className="flex items-center gap-3">
                        <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                            <Layers2Icon className="size-5" />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold">Field settings</h3>
                            <p className="text-xs text-muted-foreground">
                                Select a summary card in Compose mode to edit labels, logic, validation, and mapping.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </aside>
    )
}

function CanvasArea({
    desktopCanvasWidthClass,
    mobileCanvasWidthClass,
    canvasFrameClass,
    formName,
    formDescription,
    publicTitle,
    resolvedLogoUrl,
    privacyNotice,
    canvasMode,
    previewDevice,
    onCanvasModeChange,
    onPreviewDeviceChange,
    currentPage,
    currentPageIndex,
    totalPages,
    pages,
    selectedField,
    isDragging,
    dropIndicatorId,
    onDragOver,
    onCanvasDragOver,
    onDrop,
    onFieldDragStart,
    onFieldDragOver,
    onDropOnField,
    onDragEnd,
    onSelectField,
    onDuplicateField,
    onDeleteField,
    onOpenFieldLibrary,
    onSetActivePage,
    activePage,
}: {
    desktopCanvasWidthClass: string
    mobileCanvasWidthClass: string
    canvasFrameClass: string
    formName: string
    formDescription: string
    publicTitle: string
    resolvedLogoUrl: string
    privacyNotice: string
    canvasMode: "compose" | "preview"
    previewDevice: "desktop" | "mobile"
    onCanvasModeChange: (value: "compose" | "preview") => void
    onPreviewDeviceChange: (value: "desktop" | "mobile") => void
    currentPage: BuilderFormPage
    currentPageIndex: number
    totalPages: number
    pages: BuilderFormPage[]
    selectedField: string | null
    isDragging: boolean
    dropIndicatorId: string | "end" | null
    onDragOver: (e: React.DragEvent) => void
    onCanvasDragOver: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
    onFieldDragStart: (fieldId: string) => void
    onFieldDragOver: (e: React.DragEvent, fieldId: string) => void
    onDropOnField: (e: React.DragEvent, fieldId: string) => void
    onDragEnd: () => void
    onSelectField: (fieldId: string) => void
    onDuplicateField: (fieldId: string) => void
    onDeleteField: (fieldId: string) => void
    onOpenFieldLibrary: () => void
    onSetActivePage: (pageId: number) => void
    activePage: number
}) {
    return (
        <section data-testid="form-builder-canvas" className="min-h-0 min-w-0 overflow-y-auto bg-muted/20 p-4 sm:p-6 xl:p-8">
            <div className="mx-auto flex h-full min-h-full flex-col gap-4">
                <div className="rounded-[28px] border border-border/70 bg-card/95 p-4 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                                Active page
                            </p>
                            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
                                {currentPage.name || `Page ${currentPageIndex}`}
                            </h2>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Page {currentPageIndex} of {totalPages}
                            </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                            <Tabs
                                value={canvasMode}
                                onValueChange={(value) => onCanvasModeChange(value as "compose" | "preview")}
                                className="gap-0"
                            >
                                <TabsList aria-label="Canvas mode" className="h-auto bg-muted/70">
                                    <TabsTrigger value="compose">Compose</TabsTrigger>
                                    <TabsTrigger value="preview">Preview</TabsTrigger>
                                </TabsList>
                            </Tabs>

                            {canvasMode === "preview" ? (
                                <div className="flex items-center gap-2">
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant={previewDevice === "desktop" ? "secondary" : "outline"}
                                        onClick={() => onPreviewDeviceChange("desktop")}
                                    >
                                        <MonitorIcon className="mr-2 size-4" />
                                        Desktop Preview
                                    </Button>
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant={previewDevice === "mobile" ? "secondary" : "outline"}
                                        onClick={() => onPreviewDeviceChange("mobile")}
                                    >
                                        <SparklesIcon className="mr-2 size-4" />
                                        Mobile Preview
                                    </Button>
                                </div>
                            ) : (
                                <div className="rounded-full border border-border/70 bg-muted/30 px-3 py-1 text-xs text-muted-foreground">
                                    Drag cards to reorder within this page.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {canvasMode === "preview" ? (
                    <FormBuilderCanvasPreview
                        pages={pages}
                        activePage={activePage}
                        formName={formName}
                        formDescription={formDescription}
                        publicTitle={publicTitle}
                        resolvedLogoUrl={resolvedLogoUrl}
                        privacyNotice={privacyNotice}
                        previewDevice={previewDevice}
                        desktopWidthClass={desktopCanvasWidthClass}
                        mobileWidthClass={mobileCanvasWidthClass}
                        onSetActivePage={onSetActivePage}
                    />
                ) : (
                    <ComposeCanvas
                        desktopCanvasWidthClass={desktopCanvasWidthClass}
                        canvasFrameClass={canvasFrameClass}
                        currentPage={currentPage}
                        selectedField={selectedField}
                        isDragging={isDragging}
                        dropIndicatorId={dropIndicatorId}
                        onDragOver={onDragOver}
                        onCanvasDragOver={onCanvasDragOver}
                        onDrop={onDrop}
                        onFieldDragStart={onFieldDragStart}
                        onFieldDragOver={onFieldDragOver}
                        onDropOnField={onDropOnField}
                        onDragEnd={onDragEnd}
                        onSelectField={onSelectField}
                        onDuplicateField={onDuplicateField}
                        onDeleteField={onDeleteField}
                        onOpenFieldLibrary={onOpenFieldLibrary}
                    />
                )}
            </div>
        </section>
    )
}

export function FormBuilderWorkspace({
    desktopCanvasWidthClass,
    mobileCanvasWidthClass,
    canvasFrameClass,
    mappingOptions,
    formName,
    formDescription,
    publicTitle,
    resolvedLogoUrl,
    privacyNotice,
    canvasMode,
    previewDevice,
    fieldLibraryOpen,
    fieldLibrarySearch,
    fieldLibraryCategory,
    onCanvasModeChange,
    onPreviewDeviceChange,
    onFieldLibraryOpenChange,
    onFieldLibrarySearchChange,
    onFieldLibraryCategoryChange,
    document,
}: FormBuilderWorkspaceProps) {
    const currentPageIndex = Math.max(1, document.pages.findIndex((page) => page.id === document.activePage) + 1)

    const handleInsertFieldFromLibrary = (field: BuilderPaletteField) => {
        document.handleInsertField(field)
        onFieldLibrarySearchChange("")
        onFieldLibraryCategoryChange("all")
        onFieldLibraryOpenChange(false)
    }

    return (
        <>
            <div
                data-testid="form-builder-workspace"
                className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6 xl:grid xl:grid-cols-[280px_minmax(0,1fr)_320px] xl:gap-0 xl:overflow-hidden xl:p-0"
            >
                <PageRail
                    pages={document.pages}
                    activePage={document.activePage}
                    onSetActivePage={document.setActivePage}
                    onAddPage={document.handleAddPage}
                    onDuplicatePage={document.handleDuplicatePage}
                    onRenamePage={document.handleRenamePage}
                    onMovePage={document.handleMovePage}
                    onRequestDeletePage={document.requestDeletePage}
                    onOpenFieldLibrary={() => onFieldLibraryOpenChange(true)}
                />

                <CanvasArea
                    desktopCanvasWidthClass={desktopCanvasWidthClass}
                    mobileCanvasWidthClass={mobileCanvasWidthClass}
                    canvasFrameClass={canvasFrameClass}
                    formName={formName}
                    formDescription={formDescription}
                    publicTitle={publicTitle}
                    resolvedLogoUrl={resolvedLogoUrl}
                    privacyNotice={privacyNotice}
                    canvasMode={canvasMode}
                    previewDevice={previewDevice}
                    onCanvasModeChange={onCanvasModeChange}
                    onPreviewDeviceChange={onPreviewDeviceChange}
                    currentPage={document.currentPage}
                    currentPageIndex={currentPageIndex}
                    totalPages={document.pages.length}
                    pages={document.pages}
                    selectedField={document.selectedField}
                    isDragging={document.isDragging}
                    dropIndicatorId={document.dropIndicatorId}
                    onDragOver={document.handleDragOver}
                    onCanvasDragOver={document.handleCanvasDragOver}
                    onDrop={document.handleDrop}
                    onFieldDragStart={document.handleFieldDragStart}
                    onFieldDragOver={document.handleFieldDragOver}
                    onDropOnField={document.handleDropOnField}
                    onDragEnd={document.handleDragEnd}
                    onSelectField={document.selectField}
                    onDuplicateField={document.handleDuplicateField}
                    onDeleteField={document.handleDeleteField}
                    onOpenFieldLibrary={() => onFieldLibraryOpenChange(true)}
                    onSetActivePage={document.setActivePage}
                    activePage={document.activePage}
                />

                <FieldInspector
                    canvasMode={canvasMode}
                    currentPage={document.currentPage}
                    selectedFieldData={document.selectedFieldData}
                    mappingOptions={mappingOptions}
                    onUpdateField={document.handleUpdateField}
                    onValidationChange={document.handleValidationChange}
                    onAddColumn={document.handleAddColumn}
                    onUpdateColumn={document.handleUpdateColumn}
                    onRemoveColumn={document.handleRemoveColumn}
                    onShowIfChange={document.handleShowIfChange}
                    onMappingChange={document.handleMappingChange}
                    syncOptionKeys={document.syncOptionKeys}
                    addOption={document.addOption}
                    removeOption={document.removeOption}
                />
            </div>

            <FieldLibrarySheet
                open={fieldLibraryOpen}
                activeCategory={fieldLibraryCategory}
                search={fieldLibrarySearch}
                onOpenChange={onFieldLibraryOpenChange}
                onCategoryChange={onFieldLibraryCategoryChange}
                onSearchChange={onFieldLibrarySearchChange}
                onInsertField={handleInsertFieldFromLibrary}
            />
        </>
    )
}
