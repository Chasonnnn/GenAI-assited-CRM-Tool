"use client"

import { useMemo, useState } from "react"
import { GripVerticalIcon, PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    CUSTOM_FIELD_GROUPS,
    PRESET_FIELD_GROUPS,
    type BuilderPaletteField,
} from "@/lib/forms/form-builder-library"
import { cn } from "@/lib/utils"

type FormBuilderPaletteProps = {
    onInsertField: (field: BuilderPaletteField) => void
    onFieldDragStart: (field: BuilderPaletteField) => void
    onFieldDragEnd: () => void
    onAddPage: () => void
    className?: string
}

function PaletteFieldButton({
    field,
    ariaLabel,
    onInsertField,
    onFieldDragStart,
    onFieldDragEnd,
    className,
    iconClassName,
}: {
    field: BuilderPaletteField
    ariaLabel: string
    onInsertField: (field: BuilderPaletteField) => void
    onFieldDragStart: (field: BuilderPaletteField) => void
    onFieldDragEnd: () => void
    className?: string
    iconClassName?: string
}) {
    const IconComponent = field.icon

    return (
        <button
            type="button"
            draggable
            onClick={() => onInsertField(field)}
            onDragStart={() => onFieldDragStart(field)}
            onDragEnd={onFieldDragEnd}
            aria-label={ariaLabel}
            className={cn(
                "flex w-full cursor-grab items-center gap-3 rounded-xl border border-border/70 bg-background px-3 py-2.5 text-left text-sm font-medium transition-all hover:border-primary/40 hover:bg-muted active:cursor-grabbing",
                className,
            )}
        >
            <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/8 text-primary", iconClassName)}>
                <IconComponent className="size-4" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1 break-words">{field.label}</span>
            <GripVerticalIcon className="size-4 text-muted-foreground/70" aria-hidden="true" />
        </button>
    )
}

export function FormBuilderPalette({
    onInsertField,
    onFieldDragStart,
    onFieldDragEnd,
    onAddPage,
    className,
}: FormBuilderPaletteProps) {
    const [activePresetGroupId, setActivePresetGroupId] = useState(PRESET_FIELD_GROUPS[0]?.id ?? "")
    const activePresetGroup = useMemo(
        () => PRESET_FIELD_GROUPS.find((group) => group.id === activePresetGroupId) ?? PRESET_FIELD_GROUPS[0]!,
        [activePresetGroupId],
    )

    return (
        <div
            data-testid="form-builder-palette"
            aria-label="Field palette"
            className={cn(
                "w-full shrink-0 border-b border-border bg-card p-4 xl:min-h-0 xl:w-[320px] xl:overflow-y-auto xl:border-r xl:border-b-0",
                className,
            )}
        >
            <div className="space-y-6">
                <section className="space-y-4">
                    <div>
                        <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                            Preset Fields
                        </h3>
                        <p className="mt-1 text-xs text-muted-foreground">
                            Common surrogate intake questions, grouped by topic.
                        </p>
                    </div>

                    <div className="space-y-3 xl:grid xl:grid-cols-[104px_minmax(0,1fr)] xl:items-start xl:gap-3 xl:space-y-0">
                        <div
                            role="group"
                            aria-label="Preset field groups"
                            className="flex flex-wrap gap-2 xl:flex-col xl:rounded-2xl xl:border xl:border-border/70 xl:bg-muted/30 xl:p-2"
                        >
                            {PRESET_FIELD_GROUPS.map((group) => {
                                const isActive = group.id === activePresetGroup?.id

                                return (
                                    <button
                                        key={group.id}
                                        type="button"
                                        aria-pressed={isActive}
                                        onClick={() => setActivePresetGroupId(group.id)}
                                        className={cn(
                                            "inline-flex min-h-10 flex-none items-center justify-center rounded-xl border px-3 py-2 text-sm font-semibold transition-all xl:w-full xl:justify-start",
                                            isActive
                                                ? "border-primary/30 bg-primary/10 text-foreground shadow-sm"
                                                : "border-border/70 bg-background text-muted-foreground hover:border-primary/25 hover:text-foreground",
                                        )}
                                    >
                                        {group.label}
                                    </button>
                                )
                            })}
                        </div>

                        <div className="min-w-0 rounded-2xl border border-border/70 bg-muted/15">
                            <div className="border-b border-border/60 px-3 py-3">
                                <h4 className="text-sm font-semibold text-foreground">{activePresetGroup.label}</h4>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    Drag or click a preset field to add it to the active page.
                                </p>
                            </div>
                            <ScrollArea className="h-[320px] sm:h-[360px] xl:h-[320px]">
                                <div className="grid grid-cols-1 gap-2 p-3">
                                    {activePresetGroup.fields.map((field) => (
                                        <PaletteFieldButton
                                            key={`${activePresetGroup.id}-${field.key}`}
                                            field={field}
                                            ariaLabel={`Add preset ${field.label} field`}
                                            onInsertField={onInsertField}
                                            onFieldDragStart={onFieldDragStart}
                                            onFieldDragEnd={onFieldDragEnd}
                                        />
                                    ))}
                                </div>
                            </ScrollArea>
                        </div>
                    </div>
                </section>

                <section>
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Custom Fields
                    </h3>
                    <div className="space-y-4">
                        {CUSTOM_FIELD_GROUPS.map((group) => (
                            <div key={group.id} className="space-y-2">
                                <h4 className="text-sm font-semibold text-foreground">{group.label}</h4>
                                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1">
                                    {group.fields.map((field) => (
                                        <PaletteFieldButton
                                            key={field.key}
                                            field={field}
                                            ariaLabel={`Add ${field.label} field`}
                                            onInsertField={onInsertField}
                                            onFieldDragStart={onFieldDragStart}
                                            onFieldDragEnd={onFieldDragEnd}
                                            className="rounded-lg border-border px-3 py-3"
                                            iconClassName="size-10 rounded-lg bg-transparent text-muted-foreground"
                                        />
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                <Button
                    variant="outline"
                    size="sm"
                    className="w-full bg-transparent sm:w-auto xl:w-full"
                    onClick={onAddPage}
                >
                    <PlusIcon className="mr-2 size-4" />
                    Add Page
                </Button>
            </div>
        </div>
    )
}
