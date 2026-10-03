"use client"


import { Button } from "@/components/ui/button"
import { Command, CommandInput } from "@/components/ui/command"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    getBuilderFieldGroupsForLeadKind,
    type BuilderLibraryCategory,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import type { FormLeadKind } from "@/lib/api/forms"
import { cn } from "@/lib/utils"

type FormBuilderPaletteProps = {
    leadKind: FormLeadKind
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
        <Button unstyled
            type="button"
            data-testid={buildTileTestId(field)}
            draggable
            onClick={() => onInsertField(field)}
            onDragStart={() => onFieldDragStart(field)}
            onDragEnd={onFieldDragEnd}
            aria-label={`${isPreset ? "Add preset" : "Add"} ${field.label} field`}
            className="group flex min-h-0 flex-col items-center gap-1.5 rounded-lg border border-transparent px-1 py-2 text-center transition-colors hover:bg-muted focus-visible:border-ring active:cursor-grabbing"
        >
            <span
                className={cn(
                    "flex size-9 items-center justify-center rounded-lg border bg-background text-foreground",
                    isPreset ? "border-primary/30" : "border-border",
                )}
            >
                <Icon className="size-4" aria-hidden="true" />
            </span>
            <div className="w-full text-xs font-medium leading-tight text-foreground">{field.label}</div>
        </Button>
    )
}

export function FormBuilderPalette({
    leadKind,
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
    const { presetGroups, allGroups } = getBuilderFieldGroupsForLeadKind(leadKind)
    const presetGroupIds = new Set(presetGroups.map((group) => group.id))
    const categories: Array<{ id: BuilderLibraryCategory; label: string }> = [
        { id: ALL_CATEGORY_ID, label: "All" },
        ...allGroups.map((group) => ({ id: group.id, label: group.label })),
    ]
    const resolvedActiveCategory =
        activeCategory === ALL_CATEGORY_ID || allGroups.some((group) => group.id === activeCategory)
            ? activeCategory
            : ALL_CATEGORY_ID

    const searchPattern = normalizedSearch
        ? new RegExp(escapeRegExp(normalizedSearch), "i")
        : null
    const sourceGroups =
        normalizedSearch
            ? allGroups
            : resolvedActiveCategory === ALL_CATEGORY_ID
            ? allGroups
            : allGroups.filter((group) => group.id === resolvedActiveCategory)

    const visibleSections: VisibleSection[] = []
    for (const group of sourceGroups) {
        const section = {
            id: group.id,
            label: group.label,
            isPreset: presetGroupIds.has(group.id),
            fields: group.fields.filter((field) => {
                if (!searchPattern) return true
                return searchPattern.test(`${field.label} ${field.key}`)
            }),
        }
        if (section.fields.length > 0) visibleSections.push(section)
    }

    return (
        <div data-testid="form-builder-palette" className={cn("flex h-full min-h-0 flex-col", className)}>
            <div className="space-y-3 border-b border-border/70 p-3">
                <div data-testid="form-builder-palette-search" className="rounded-lg border border-border bg-background">
                    <Command className="rounded-lg border-0 bg-transparent p-0 shadow-none">
                        <CommandInput
                            className="text-sm placeholder:text-muted-foreground"
                            value={search}
                            onValueChange={onSearchChange}
                            placeholder="Search form fields"
                        />
                    </Command>
                </div>
                <nav className="flex flex-wrap gap-1.5" aria-label="Field categories">
                    {categories.map((category) => {
                        const isActive = resolvedActiveCategory === category.id

                        return (
                            <Button unstyled
                                key={category.id}
                                type="button"
                                aria-pressed={isActive}
                                onClick={() => onCategoryChange(category.id)}
                                className={cn(
                                    "h-7 rounded-full border px-2.5 text-xs font-medium transition-colors",
                                    isActive
                                        ? "border-foreground bg-foreground text-background"
                                        : "border-border bg-background text-foreground hover:bg-muted",
                                )}
                            >
                                {category.label}
                            </Button>
                        )
                    })}
                </nav>
            </div>

            <ScrollArea className="min-h-0 flex-1">
                <div className="space-y-5 p-3">
                    {visibleSections.length > 0 ? (
                        visibleSections.map((section) => (
                            <section key={section.id} className="space-y-2">
                                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                    {section.label}
                                </h3>
                                <div data-testid="form-builder-palette-field-grid" className="grid grid-cols-3 gap-1">
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
                        <p className="py-6 text-center text-sm text-muted-foreground">No matching fields</p>
                    )}
                </div>
            </ScrollArea>
        </div>
    )
}
