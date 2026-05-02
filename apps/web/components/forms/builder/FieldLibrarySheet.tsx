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
                "group flex min-h-0 flex-col items-center gap-1.5 rounded-xl border border-transparent px-1.5 py-2 text-center transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isPreset
                    ? "hover:bg-sky-50/75 focus-visible:border-sky-200"
                    : "hover:bg-emerald-50/70 focus-visible:border-emerald-200",
            )}
        >
            <span
                className={cn(
                    "flex size-12 items-center justify-center rounded-2xl border transition-transform group-hover:scale-[1.02]",
                    isPreset
                        ? "border-sky-200/90 bg-sky-50/70 text-slate-900"
                        : "border-emerald-200/90 bg-emerald-50/65 text-slate-900",
                )}
            >
                <Icon className="size-4" aria-hidden="true" />
            </span>
            <span className="w-full text-[13px] font-medium leading-tight text-slate-900">{field.label}</span>
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
                    <SheetHeader className="border-b border-border/70 px-6 py-4">
                        <SheetTitle className="text-xl font-semibold tracking-tight">Add form fields</SheetTitle>
                        <SheetDescription>Search and add fields for the active page.</SheetDescription>
                    </SheetHeader>

                    <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[12rem_minmax(0,1fr)]">
                        <aside className="border-b border-border/70 bg-stone-50/75 md:border-r md:border-b-0">
                            <ScrollArea className="h-full">
                                <div className="space-y-1 p-2.5">
                                    {categories.map((category) => {
                                        const isActive = activeCategory === category.id

                                        return (
                                            <button
                                                key={category.id}
                                                type="button"
                                                onClick={() => onCategoryChange(category.id)}
                                                className={cn(
                                                    "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[15px] font-medium leading-5 transition-all",
                                                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                                    isActive
                                                        ? "bg-sky-100/90 text-slate-950"
                                                        : "text-slate-700 hover:bg-white/90 hover:text-slate-950",
                                                )}
                                            >
                                                {category.label}
                                            </button>
                                        )
                                    })}
                                </div>
                            </ScrollArea>
                        </aside>

                        <div className="flex min-h-0 flex-col bg-white">
                            <div className="border-b border-border/70 bg-white/95 px-4 py-3 supports-[backdrop-filter]:bg-white/80">
                                <div className="rounded-xl border border-stone-200/80 bg-white shadow-none">
                                    <Command className="rounded-xl border-0 bg-transparent p-0 shadow-none">
                                        <CommandInput
                                            className="text-[15px] placeholder:text-slate-400"
                                            value={search}
                                            onValueChange={onSearchChange}
                                            placeholder="Search form fields"
                                        />
                                    </Command>
                                </div>
                            </div>

                            <ScrollArea className="min-h-0 flex-1">
                                <div className="space-y-6 p-4">
                                    {visibleSections.length > 0 ? (
                                        visibleSections.map((section) => (
                                            <section key={section.id} className="space-y-3">
                                                <h3 className="text-[15px] font-semibold tracking-tight text-slate-950">
                                                    {section.label}
                                                </h3>
                                                <div className="grid grid-cols-4 gap-x-1.5 gap-y-2.5">
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
                                        <div className="rounded-[22px] border border-dashed border-border/80 bg-stone-50 p-8 text-center">
                                            <p className="text-base font-semibold text-slate-900">No matching fields</p>
                                            <p className="mt-1.5 text-sm text-slate-500">
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
