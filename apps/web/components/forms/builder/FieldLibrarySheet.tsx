"use client"

import { useMemo } from "react"

import { Command, CommandInput } from "@/components/ui/command"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import {
    ALL_BUILDER_FIELD_GROUPS,
    CUSTOM_FIELD_GROUPS,
    PRESET_FIELD_GROUPS,
    type BuilderLibraryCategory,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import { cn } from "@/lib/utils"

type FieldLibrarySheetProps = {
    open: boolean
    activeCategory: BuilderLibraryCategory
    search: string
    onOpenChange: (open: boolean) => void
    onCategoryChange: (value: BuilderLibraryCategory) => void
    onSearchChange: (value: string) => void
    onInsertField: (field: BuilderPaletteField) => void
}

type LibrarySection = {
    id: string
    label: string
    isPreset: boolean
    fields: BuilderPaletteField[]
}

const ALL_CATEGORY_ID = "all"

function buildTileAriaLabel(field: BuilderPaletteField, isPreset: boolean) {
    return `${isPreset ? "Add preset" : "Add"} ${field.label} field`
}

function FieldTile({
    field,
    isPreset,
    onInsertField,
}: {
    field: BuilderPaletteField
    isPreset: boolean
    onInsertField: (field: BuilderPaletteField) => void
}) {
    const Icon = field.icon

    return (
        <button
            type="button"
            aria-label={buildTileAriaLabel(field, isPreset)}
            onClick={() => onInsertField(field)}
            className={cn(
                "group flex min-h-[138px] flex-col items-start justify-between rounded-[28px] border px-4 py-4 text-left transition-all",
                isPreset
                    ? "border-sky-200/80 bg-sky-50/80 hover:border-sky-300 hover:bg-sky-50"
                    : "border-emerald-200/80 bg-emerald-50/70 hover:border-emerald-300 hover:bg-emerald-50",
            )}
        >
            <span
                className={cn(
                    "flex size-14 items-center justify-center rounded-2xl border transition-transform group-hover:scale-[1.03]",
                    isPreset
                        ? "border-sky-200 bg-white text-slate-900"
                        : "border-emerald-200 bg-white text-slate-900",
                )}
            >
                <Icon className="size-6" aria-hidden="true" />
            </span>
            <span className="text-base font-semibold text-slate-900">{field.label}</span>
        </button>
    )
}

export function FieldLibrarySheet({
    open,
    activeCategory,
    search,
    onOpenChange,
    onCategoryChange,
    onSearchChange,
    onInsertField,
}: FieldLibrarySheetProps) {
    const normalizedSearch = search.trim().toLowerCase()

    const categories = useMemo(
        () => [
            { id: ALL_CATEGORY_ID, label: "All" },
            ...PRESET_FIELD_GROUPS.map((group) => ({ id: group.id, label: group.label })),
            ...CUSTOM_FIELD_GROUPS.map((group) => ({ id: group.id, label: group.label })),
        ],
        [],
    )

    const visibleSections = useMemo<LibrarySection[]>(() => {
        const sourceGroups =
            normalizedSearch
                ? ALL_BUILDER_FIELD_GROUPS
                : activeCategory === ALL_CATEGORY_ID
                ? ALL_BUILDER_FIELD_GROUPS
                : ALL_BUILDER_FIELD_GROUPS.filter((group) => group.id === activeCategory)

        return sourceGroups
            .map((group) => ({
                id: group.id,
                label: group.label,
                isPreset: PRESET_FIELD_GROUPS.some((presetGroup) => presetGroup.id === group.id),
                fields: group.fields.filter((field) => {
                    if (!normalizedSearch) return true
                    return `${field.label} ${field.key}`.toLowerCase().includes(normalizedSearch)
                }),
            }))
            .filter((section) => section.fields.length > 0)
    }, [activeCategory, normalizedSearch])

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full p-0 sm:max-w-[980px]">
                <div className="flex h-full flex-col">
                    <SheetHeader className="border-b border-border/70 px-6 py-5">
                        <SheetTitle className="text-[2rem] font-semibold tracking-tight">Add form fields</SheetTitle>
                        <SheetDescription>
                            Search or browse recommended intake fields and custom controls for the active page.
                        </SheetDescription>
                    </SheetHeader>

                    <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[232px_minmax(0,1fr)]">
                        <aside className="border-b border-border/70 bg-stone-50/90 md:border-r md:border-b-0">
                            <ScrollArea className="h-full">
                                <div className="space-y-2 p-4">
                                    {categories.map((category) => {
                                        const isActive = activeCategory === category.id

                                        return (
                                            <button
                                                key={category.id}
                                                type="button"
                                                onClick={() => onCategoryChange(category.id)}
                                                className={cn(
                                                    "flex w-full items-center justify-between rounded-2xl px-4 py-3 text-left text-base font-medium transition-all",
                                                    isActive
                                                        ? "bg-sky-100 text-slate-950 shadow-sm"
                                                        : "text-slate-700 hover:bg-white hover:text-slate-950",
                                                )}
                                            >
                                                {category.label}
                                            </button>
                                        )
                                    })}
                                </div>
                            </ScrollArea>
                        </aside>

                        <div className="min-h-0 bg-white">
                            <div className="border-b border-border/70 p-4">
                                <Command className="rounded-[28px] border border-border/70 bg-stone-50/80 p-2">
                                    <CommandInput
                                        value={search}
                                        onValueChange={onSearchChange}
                                        placeholder="Search form fields"
                                    />
                                </Command>
                            </div>

                            <ScrollArea className="h-[calc(100vh-180px)]">
                                <div className="space-y-10 p-6">
                                    {visibleSections.length > 0 ? (
                                        visibleSections.map((section) => (
                                            <section key={section.id} className="space-y-4">
                                                <div className="space-y-1">
                                                    <h3 className="text-2xl font-semibold tracking-tight text-slate-950">
                                                        {section.label}
                                                    </h3>
                                                    <p className="text-sm text-slate-500">
                                                        {section.isPreset
                                                            ? "Recommended surrogate intake fields."
                                                            : "Custom builder controls for this form."}
                                                    </p>
                                                </div>
                                                <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
                                                    {section.fields.map((field) => (
                                                        <FieldTile
                                                            key={`${section.id}-${field.key}`}
                                                            field={field}
                                                            isPreset={section.isPreset}
                                                            onInsertField={onInsertField}
                                                        />
                                                    ))}
                                                </div>
                                            </section>
                                        ))
                                    ) : (
                                        <div className="rounded-[28px] border border-dashed border-border/80 bg-stone-50 p-10 text-center">
                                            <p className="text-lg font-semibold text-slate-900">No matching fields</p>
                                            <p className="mt-2 text-sm text-slate-500">
                                                Try a different search or switch categories.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </ScrollArea>
                        </div>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    )
}
