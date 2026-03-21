"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FormBuilderPalette } from "@/components/forms/FormBuilderPalette"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FormBuilderFieldPreview } from "@/components/forms/FormBuilderFieldPreview"
import {
    getBuilderFieldIcon,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import {
    parseOptionalInt,
    parseOptionalNumber,
    type BuilderFormField,
    type BuilderFormPage,
} from "@/lib/forms/form-builder-document"
import type { FormFieldValidation, FormSurrogateFieldOption } from "@/lib/api/forms"
import {
    CopyIcon,
    GripVerticalIcon,
    PlusIcon,
    Trash2Icon,
    TypeIcon,
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
    paletteWidthClass: string
    canvasWidthClass: string
    canvasFrameClass: string
    canvasScaleClass: string
    canvasTypographyClass: string
    mappingOptions: FormSurrogateFieldOption[]
    document: WorkspaceDocument
}

type PaletteRailProps = {
    paletteWidthClass: string
    onAddPage: () => void
    onInsertField: (field: BuilderPaletteField) => void
    onDragStart: (field: BuilderPaletteField) => void
    onDragEnd: () => void
}

function PaletteRail({
    paletteWidthClass,
    onAddPage,
    onInsertField,
    onDragStart,
    onDragEnd,
}: PaletteRailProps) {
    return (
        <FormBuilderPalette
            className={paletteWidthClass}
            onInsertField={onInsertField}
            onFieldDragStart={onDragStart}
            onFieldDragEnd={onDragEnd}
            onAddPage={onAddPage}
        />
    )
}

type CanvasAreaProps = {
    canvasWidthClass: string
    canvasFrameClass: string
    canvasScaleClass: string
    canvasTypographyClass: string
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
    onUpdateField: (fieldId: string, updates: Partial<BuilderFormField>) => void
    onDuplicateField: (fieldId: string) => void
    onDeleteField: (fieldId: string) => void
}

function CanvasArea({
    canvasWidthClass,
    canvasFrameClass,
    canvasScaleClass,
    canvasTypographyClass,
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
    onUpdateField,
    onDuplicateField,
    onDeleteField,
}: CanvasAreaProps) {
    return (
        <div
            data-testid="form-builder-canvas"
            className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-muted/20 p-4 sm:p-6 xl:p-8"
        >
            <div
                onDragOver={onCanvasDragOver}
                onDrop={onDrop}
                className={`mx-auto min-h-[500px] ${canvasWidthClass} space-y-4 ${
                    currentPage.fields.length === 0 ? "flex items-center justify-center" : ""
                } ${canvasFrameClass} ${canvasScaleClass} ${canvasTypographyClass}`}
            >
                {currentPage.fields.length === 0 ? (
                    <div
                        onDragOver={onDragOver}
                        onDrop={onDrop}
                        className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border/80 p-8 text-center sm:p-12"
                    >
                        <div className="mb-4 flex size-20 items-center justify-center rounded-full bg-primary/10">
                            <TypeIcon className="size-10 text-primary" />
                        </div>
                        <h3 className="mb-2 text-lg font-semibold">Drag fields here to build your form</h3>
                        <p className="text-sm text-muted-foreground">
                            Start by dragging fields from the left sidebar
                        </p>
                    </div>
                ) : (
                    <>
                        {currentPage.fields.map((field) => {
                            const IconComponent = getBuilderFieldIcon(field.type)
                            return (
                                <div key={field.id} className="space-y-2">
                                    {isDragging && dropIndicatorId === field.id && (
                                        <div className="h-0.5 rounded-full bg-primary" />
                                    )}
                            <Card
                                draggable
                                onDragStart={() => onFieldDragStart(field.id)}
                                onDragOver={(e) => onFieldDragOver(e, field.id)}
                                onDrop={(e) => onDropOnField(e, field.id)}
                                onDragEnd={onDragEnd}
                                className={`cursor-pointer gap-0 rounded-2xl border border-border bg-card py-0 transition-all hover:border-primary/30 hover:shadow-sm ${
                                    selectedField === field.id ? "border-primary/40 ring-2 ring-primary/20" : ""
                                }`}
                                onClick={() => onSelectField(field.id)}
                            >
                                <CardContent className="flex items-start gap-3 p-4 sm:p-5">
                                    <GripVerticalIcon className="mt-1 size-5 cursor-grab text-muted-foreground/70" />
                                    <IconComponent className="mt-1 size-5 text-primary" />
                                    <div className="flex-1">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="min-w-0 flex-1">
                                                        <div className="flex items-start gap-2">
                                                            <Input
                                                                draggable={false}
                                                                value={field.label}
                                                                onChange={(e) => onUpdateField(field.id, { label: e.target.value })}
                                                                className="h-auto border-none bg-transparent p-0 text-base font-medium focus-visible:ring-0"
                                                                onClick={(e) => e.stopPropagation()}
                                                            />
                                                            {field.required && (
                                                                <span className="pt-0.5 text-red-500">*</span>
                                                            )}
                                                        </div>
                                                        <FormBuilderFieldPreview
                                                            label={field.label}
                                                            type={field.type}
                                                            surrogateFieldMapping={field.surrogateFieldMapping}
                                                            options={field.options}
                                                            columns={field.columns}
                                                        />
                                                        {field.helperText && (
                                                            <p className="mt-2 text-sm text-muted-foreground">
                                                                {field.helperText}
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                    <div className="flex items-center gap-0.5">
                                        <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="shrink-0"
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        onDuplicateField(field.id)
                                                    }}
                                                    aria-label={`Duplicate ${field.label || "field"}`}
                                                >
                                                    <CopyIcon className="size-4" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="shrink-0"
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        onDeleteField(field.id)
                                                    }}
                                                    aria-label={`Delete ${field.label || "field"}`}
                                                >
                                                    <XIcon className="size-4" />
                                                </Button>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>
                            )
                        })}
                        {isDragging && dropIndicatorId === "end" && (
                            <div className="h-0.5 rounded-full bg-primary" />
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

type FieldInspectorProps = {
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
    onShowIfChange,
    onMappingChange,
    syncOptionKeys,
    addOption,
    removeOption,
}: FieldInspectorProps) {
    return (
        <div
            data-testid="form-builder-settings"
            aria-label="Form builder settings"
            className="w-full shrink-0 border-t border-border bg-card p-4 xl:min-h-0 xl:w-[280px] xl:overflow-y-auto xl:border-l xl:border-t-0"
        >
            {selectedFieldData ? (
                <div className="space-y-6">
                    <div>
                        <h3 className="mb-4 text-sm font-semibold">Field Settings</h3>

                        <div className="space-y-2">
                            <Label htmlFor="field-label">Label</Label>
                            <Input
                                id="field-label"
                                value={selectedFieldData.label}
                                onChange={(e) => onUpdateField(selectedFieldData.id, { label: e.target.value })}
                            />
                        </div>

                        <div className="mt-4 space-y-2">
                            <Label htmlFor="field-helper">Helper Text</Label>
                            <Input
                                id="field-helper"
                                value={selectedFieldData.helperText}
                                onChange={(e) => onUpdateField(selectedFieldData.id, { helperText: e.target.value })}
                                placeholder="Optional hint for users"
                            />
                        </div>

                        <div className="mt-4 flex items-center justify-between">
                            <Label htmlFor="field-required">Required</Label>
                            <Switch
                                id="field-required"
                                checked={selectedFieldData.required}
                                onCheckedChange={(checked) => onUpdateField(selectedFieldData.id, { required: checked })}
                            />
                        </div>

                        <div className="mt-4 space-y-3">
                            <div className="flex items-center justify-between">
                                <Label>Display Rules</Label>
                                {selectedFieldData.showIf && (
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => onUpdateField(selectedFieldData.id, { showIf: null })}
                                    >
                                        Clear rule
                                    </Button>
                                )}
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

                            {selectedFieldData.showIf && (
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

                                    {!["is_empty", "is_not_empty"].includes(selectedFieldData.showIf.operator) &&
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
                                                    onChange={(e) =>
                                                        onShowIfChange(selectedFieldData.id, { value: e.target.value })
                                                    }
                                                    placeholder="Value to match"
                                                />
                                            )
                                        })()}
                                </>
                            )}
                        </div>

                        {["text", "textarea", "email", "phone", "address"].includes(selectedFieldData.type) && (
                            <div className="mt-4 space-y-2">
                                <Label>Validation</Label>
                                <div className="grid grid-cols-2 gap-2">
                                    <Input
                                        inputMode="numeric"
                                        placeholder="Min length"
                                        value={selectedFieldData.validation?.min_length ?? ""}
                                        onChange={(e) =>
                                            onValidationChange(selectedFieldData.id, {
                                                min_length: parseOptionalNumber(e.target.value),
                                            })
                                        }
                                    />
                                    <Input
                                        inputMode="numeric"
                                        placeholder="Max length"
                                        value={selectedFieldData.validation?.max_length ?? ""}
                                        onChange={(e) =>
                                            onValidationChange(selectedFieldData.id, {
                                                max_length: parseOptionalNumber(e.target.value),
                                            })
                                        }
                                    />
                                </div>
                                <Input
                                    placeholder="Regex pattern (optional)"
                                    value={selectedFieldData.validation?.pattern ?? ""}
                                    onChange={(e) =>
                                        onValidationChange(selectedFieldData.id, {
                                            pattern: e.target.value,
                                        })
                                    }
                                />
                            </div>
                        )}

                        {selectedFieldData.type === "number" && (
                            <div className="mt-4 space-y-2">
                                <Label>Validation</Label>
                                <div className="grid grid-cols-2 gap-2">
                                    <Input
                                        inputMode="numeric"
                                        placeholder="Min value"
                                        value={selectedFieldData.validation?.min_value ?? ""}
                                        onChange={(e) =>
                                            onValidationChange(selectedFieldData.id, {
                                                min_value: parseOptionalNumber(e.target.value),
                                            })
                                        }
                                    />
                                    <Input
                                        inputMode="numeric"
                                        placeholder="Max value"
                                        value={selectedFieldData.validation?.max_value ?? ""}
                                        onChange={(e) =>
                                            onValidationChange(selectedFieldData.id, {
                                                max_value: parseOptionalNumber(e.target.value),
                                            })
                                        }
                                    />
                                </div>
                            </div>
                        )}

                        {selectedFieldData.type === "repeatable_table" && (
                            <div className="mt-4 space-y-3">
                                <Label>Table Columns</Label>
                                <div className="grid grid-cols-2 gap-2">
                                    <Input
                                        inputMode="numeric"
                                        placeholder="Min rows"
                                        value={selectedFieldData.minRows ?? ""}
                                        onChange={(e) =>
                                            onUpdateField(selectedFieldData.id, {
                                                minRows: parseOptionalInt(e.target.value),
                                            })
                                        }
                                    />
                                    <Input
                                        inputMode="numeric"
                                        placeholder="Max rows"
                                        value={selectedFieldData.maxRows ?? ""}
                                        onChange={(e) =>
                                            onUpdateField(selectedFieldData.id, {
                                                maxRows: parseOptionalInt(e.target.value),
                                            })
                                        }
                                    />
                                </div>
                                <div className="space-y-3">
                                    {(selectedFieldData.columns || []).map((column) => (
                                        <div
                                            key={column.id}
                                            className="rounded-lg border border-stone-200 p-3"
                                        >
                                            <div className="flex items-center gap-2">
                                                <Input
                                                    value={column.label}
                                                    onChange={(e) =>
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            label: e.target.value,
                                                        })
                                                    }
                                                    placeholder="Column label"
                                                />
                                                <Select
                                                    value={column.type}
                                                    onValueChange={(value) => {
                                                        const nextType = (value ?? "text") as
                                                            | "text"
                                                            | "number"
                                                            | "date"
                                                            | "select"
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            type: nextType,
                                                            options:
                                                                nextType === "select"
                                                                    ? column.options || ["Option 1", "Option 2"]
                                                                    : [],
                                                        })
                                                    }}
                                                >
                                                    <SelectTrigger className="w-[120px]">
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
                                            {column.type === "select" && (
                                                <Input
                                                    className="mt-2"
                                                    value={(column.options || []).join(", ")}
                                                    onChange={(e) =>
                                                        onUpdateColumn(selectedFieldData.id, column.id, {
                                                            options: e.target.value
                                                                .split(",")
                                                                .map((entry) => entry.trim())
                                                                .filter(Boolean),
                                                        })
                                                    }
                                                    placeholder="Options (comma separated)"
                                                />
                                            )}
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
                            </div>
                        )}

                        {selectedFieldData.options && (
                            <div className="mt-4 space-y-2">
                                <Label>Options</Label>
                                {(() => {
                                    const optionKeys = syncOptionKeys(selectedFieldData.id, selectedFieldData.options.length)
                                    return selectedFieldData.options.map((option, index) => (
                                        <div key={optionKeys[index]} className="flex gap-2">
                                            <Input
                                                value={option}
                                                onChange={(e) => {
                                                    const newOptions = [...selectedFieldData.options!]
                                                    newOptions[index] = e.target.value
                                                    onUpdateField(selectedFieldData.id, { options: newOptions })
                                                }}
                                            />
                                            <Button
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
                                    variant="outline"
                                    size="sm"
                                    className="w-full bg-transparent"
                                    onClick={() => addOption(selectedFieldData.id)}
                                >
                                    <PlusIcon className="mr-2 size-4" />
                                    Add Option
                                </Button>
                            </div>
                        )}
                    </div>

                    <div className="border-t border-stone-200 pt-6 dark:border-stone-800">
                        <h3 className="mb-3 text-sm font-semibold">Field Mapping</h3>
                        <p className="mb-3 text-xs text-stone-500 dark:text-stone-400">
                            Map this field to a Surrogate field to auto-populate data
                        </p>
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
                    </div>
                </div>
            ) : (
                <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-800 dark:bg-stone-900">
                    <p className="text-xs text-stone-600 dark:text-stone-400">
                        Select a field from the canvas to edit its settings, or use the Settings tab for form-wide controls.
                    </p>
                </div>
            )}
        </div>
    )
}

export function FormBuilderWorkspace({
    paletteWidthClass,
    canvasWidthClass,
    canvasFrameClass,
    canvasScaleClass,
    canvasTypographyClass,
    mappingOptions,
    document,
}: FormBuilderWorkspaceProps) {
    return (
        <>
            <div className="border-b border-border bg-background/95 px-4 py-2 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <Tabs
                        value={String(document.activePage)}
                        onValueChange={(value) => document.setActivePage(Number(value))}
                        className="gap-0"
                    >
                        <TabsList aria-label="Form pages" className="h-auto flex-wrap bg-muted/70">
                            {document.pages.map((page) => (
                                <TabsTrigger key={page.id} value={String(page.id)} className="flex-none">
                                    {page.name}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                    <div className="flex flex-wrap items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={document.handleAddPage}>
                            <PlusIcon className="mr-1 size-4" />
                            Add Page
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => document.handleDuplicatePage(document.activePage)}
                        >
                            <CopyIcon className="mr-1 size-4" />
                            Duplicate Page
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => document.requestDeletePage(document.activePage)}
                            disabled={document.pages.length === 1}
                        >
                            <Trash2Icon className="mr-1 size-4" />
                            Delete Page
                        </Button>
                    </div>
                </div>
            </div>

            <div data-testid="form-builder-workspace" className="flex min-h-0 flex-1 flex-col overflow-y-auto xl:flex-row xl:overflow-hidden">
                <PaletteRail
                    paletteWidthClass={paletteWidthClass}
                    onAddPage={document.handleAddPage}
                    onInsertField={document.handleInsertField}
                    onDragStart={document.handleDragStart}
                    onDragEnd={document.handleDragEnd}
                />
                <CanvasArea
                    canvasWidthClass={canvasWidthClass}
                    canvasFrameClass={canvasFrameClass}
                    canvasScaleClass={canvasScaleClass}
                    canvasTypographyClass={canvasTypographyClass}
                    currentPage={document.currentPage}
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
                    onUpdateField={document.handleUpdateField}
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
                    onShowIfChange={document.handleShowIfChange}
                    onMappingChange={document.handleMappingChange}
                    syncOptionKeys={document.syncOptionKeys}
                    addOption={document.addOption}
                    removeOption={document.removeOption}
                />
            </div>
        </>
    )
}
