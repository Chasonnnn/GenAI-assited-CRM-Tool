"use client"

import { Command, CommandInput } from "@/components/ui/command"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    ALL_BUILDER_FIELD_GROUPS,
    CUSTOM_FIELD_GROUPS,
    PRESET_FIELD_GROUPS,
    type BuilderLibraryCategory,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import { cn } from "@/lib/utils"

type FormBuilderPaletteProps = {
    activeCategory: BuilderLibraryCategory
    search: string
    onCategoryChange: (value: BuilderLibraryCategory) => void
    onSearchChange: (value: string) => void
    onInsertField: (field: BuilderPaletteField) => void
    onFieldDragStart: (field: BuilderPaletteField) => void
    onFieldDragEnd: () => void
    className?: string
}

type VisibleSection = {
    id: string
    label: string
    isPreset: boolean
    fields: BuilderPaletteField[]
}

const ALL_CATEGORY_ID = "all"
const PRESET_FIELD_GROUP_IDS = new Set(PRESET_FIELD_GROUPS.map((group) => group.id))
const FORM_BUILDER_PALETTE_CATEGORIES: Array<{ id: BuilderLibraryCategory; label: string }> = [
    { id: ALL_CATEGORY_ID, label: "All" },
    ...PRESET_FIELD_GROUPS.map((group) => ({ id: group.id, label: group.label })),
    ...CUSTOM_FIELD_GROUPS.map((group) => ({ id: group.id, label: group.label })),
]

function buildTileTestId(field: BuilderPaletteField) {
    return `form-builder-palette-tile-${field.key}`
}

function escapeRegExp(value: string) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function PaletteFieldTile({
    field,
    isPreset,
    onInsertField,
    onFieldDragStart,
    onFieldDragEnd,
}: {
    field: BuilderPaletteField
    isPreset: boolean
    onInsertField: (field: BuilderPaletteField) => void
    onFieldDragStart: (field: BuilderPaletteField) => void
    onFieldDragEnd: () => void
}) {
    const Icon = field.icon

    return (
        <button
            type="button"
            data-testid={buildTileTestId(field)}
            draggable
            onClick={() => onInsertField(field)}
            onDragStart={() => onFieldDragStart(field)}
            onDragEnd={onFieldDragEnd}
            aria-label={`${isPreset ? "Add preset" : "Add"} ${field.label} field`}
            className={cn(
                "group flex min-h-0 flex-col items-center gap-1.5 rounded-xl border border-transparent px-1.5 py-2 text-center transition-colors active:cursor-grabbing",
                isPreset
                    ? "hover:bg-sky-50/75 focus-visible:border-sky-200"
                    : "hover:bg-emerald-50/70 focus-visible:border-emerald-200",
            )}
        >
            <span
                className={cn(
                    "flex size-12 items-center justify-center rounded-2xl border bg-white text-zinc-900 transition-transform group-hover:scale-[1.02]",
                    isPreset
                        ? "border-sky-200/90 bg-sky-50/70"
                        : "border-emerald-200/90 bg-emerald-50/65",
                )}
            >
                <Icon className="size-4" aria-hidden="true" />
            </span>
            <div className="w-full text-[13px] font-medium leading-tight text-zinc-950">{field.label}</div>
        </button>
    )
}

export function FormBuilderPalette({
    activeCategory,
    search,
    onCategoryChange,
    onSearchChange,
    onInsertField,
    onFieldDragStart,
    onFieldDragEnd,
    className,
}: FormBuilderPaletteProps) {
    const normalizedSearch = search.trim().toLowerCase()

    const categories = FORM_BUILDER_PALETTE_CATEGORIES

    const searchPattern = normalizedSearch
        ? new RegExp(escapeRegExp(normalizedSearch), "i")
        : null
    const sourceGroups =
        normalizedSearch
            ? ALL_BUILDER_FIELD_GROUPS
            : activeCategory === ALL_CATEGORY_ID
            ? ALL_BUILDER_FIELD_GROUPS
            : ALL_BUILDER_FIELD_GROUPS.filter((group) => group.id === activeCategory)

    const visibleSections: VisibleSection[] = []
    for (const group of sourceGroups) {
        const section = {
            id: group.id,
            label: group.label,
            isPreset: PRESET_FIELD_GROUP_IDS.has(group.id),
            fields: group.fields.filter((field) => {
                if (!searchPattern) return true
                return searchPattern.test(`${field.label} ${field.key}`)
            }),
        }
        if (section.fields.length > 0) visibleSections.push(section)
    }

    return (
        <aside
            data-testid="form-builder-palette"
            aria-label="Field palette"
            className={cn(
                "w-full shrink-0 border-b border-border bg-card xl:min-h-0 xl:min-w-0 xl:w-auto xl:overflow-hidden xl:border-r xl:border-b-0",
                className,
            )}
        >
            <div className="flex h-full min-h-0 flex-col">
                <div className="border-b border-border/70 p-4">
                    <h2 className="text-[1.05rem] font-semibold tracking-tight text-zinc-950">Add form fields</h2>
                </div>

                <div className="grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[8rem_minmax(0,1fr)]">
                    <aside className="border-b border-border/70 bg-stone-50/75 xl:border-r xl:border-b-0">
                        <ScrollArea className="h-full">
                            <nav className="space-y-1 p-2.5" aria-label="Field categories">
                                {categories.map((category) => {
                                    const isActive = activeCategory === category.id

                                    return (
                                        <button
                                            key={category.id}
                                            type="button"
                                            onClick={() => onCategoryChange(category.id)}
                                            className={cn(
                                                "flex w-full items-center rounded-lg px-3 py-2 text-left text-[15px] font-medium leading-5 transition-all",
                                                isActive
                                                    ? "bg-sky-100/90 text-zinc-950"
                                                    : "text-zinc-700 hover:bg-white/90 hover:text-zinc-950",
                                            )}
                                        >
                                            {category.label}
                                        </button>
                                    )
                                })}
                            </nav>
                        </ScrollArea>
                    </aside>

                    <div className="flex min-h-0 flex-col bg-white">
                        <div className="border-b border-border/70 bg-white/95 px-4 py-3 supports-[backdrop-filter]:bg-white/80">
                            <div
                                data-testid="form-builder-palette-search"
                                className="rounded-xl border border-stone-200/80 bg-white shadow-none"
                            >
                                <Command className="rounded-xl border-0 bg-transparent p-0 shadow-none">
                                    <CommandInput
                                        className="text-[15px] placeholder:text-zinc-400"
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
                                            <h3 className="text-[15px] font-semibold tracking-tight text-zinc-950">
                                                {section.label}
                                            </h3>
                                            <div
                                                data-testid="form-builder-palette-field-grid"
                                                className="grid grid-cols-4 gap-x-1.5 gap-y-2.5"
                                            >
                                                {section.fields.map((field) => (
                                                    <PaletteFieldTile
                                                        key={`${section.id}-${field.key}`}
                                                        field={field}
                                                        isPreset={section.isPreset}
                                                        onInsertField={onInsertField}
                                                        onFieldDragStart={onFieldDragStart}
                                                        onFieldDragEnd={onFieldDragEnd}
                                                    />
                                                ))}
                                            </div>
                                        </section>
                                    ))
                                ) : (
                                    <div className="rounded-[22px] border border-dashed border-border/80 bg-stone-50 p-8 text-center">
                                        <p className="text-base font-semibold text-zinc-900">No matching fields</p>
                                        <p className="mt-1.5 text-sm text-zinc-500">
                                            Try a different search or switch categories.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </ScrollArea>
                    </div>
                </div>
            </div>
        </aside>
    )
}
