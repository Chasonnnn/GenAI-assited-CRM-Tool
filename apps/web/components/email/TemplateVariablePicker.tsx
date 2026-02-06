"use client"

import { useMemo, useState } from "react"
import { CodeIcon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandShortcut } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { TemplateVariableRead } from "@/lib/types/template-variable"

interface TemplateVariablePickerProps {
    variables: TemplateVariableRead[]
    onSelect: (variable: TemplateVariableRead) => void
    disabled?: boolean
    triggerLabel?: string
    align?: "start" | "center" | "end"
}

export function TemplateVariablePicker({
    variables,
    onSelect,
    disabled = false,
    triggerLabel = "Insert Variable",
    align = "end",
}: TemplateVariablePickerProps) {
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState("")

    const grouped = useMemo(() => {
        const map = new Map<string, TemplateVariableRead[]>()
        for (const variable of variables) {
            const key = variable.category?.trim() ? variable.category : "Other"
            const existing = map.get(key)
            if (existing) {
                existing.push(variable)
            } else {
                map.set(key, [variable])
            }
        }

        const entries = Array.from(map.entries()).map(([category, items]) => ({
            category,
            items: items.slice().sort((a, b) => a.name.localeCompare(b.name)),
        }))

        entries.sort((a, b) => a.category.localeCompare(b.category))
        return entries
    }, [variables])

    const filteredGroups = useMemo(() => {
        const q = query.trim().toLowerCase()
        if (!q) return grouped
        return grouped
            .map((group) => ({
                ...group,
                items: group.items.filter((v) => {
                    const haystack = `${v.name} ${v.description} ${v.category}`.toLowerCase()
                    return haystack.includes(q)
                }),
            }))
            .filter((group) => group.items.length > 0)
    }, [grouped, query])

    const totalFiltered = useMemo(
        () => filteredGroups.reduce((acc, g) => acc + g.items.length, 0),
        [filteredGroups]
    )

    const handleOpenChange = (next: boolean) => {
        setOpen(next)
        if (!next) setQuery("")
    }

    return (
        <Popover open={open} onOpenChange={handleOpenChange}>
            <PopoverTrigger
                render={
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={disabled}
                        className="h-8"
                    >
                        <CodeIcon className="mr-2 size-4" />
                        {triggerLabel}
                    </Button>
                }
            />
            <PopoverContent className="w-[420px] max-w-[90vw] gap-0 p-0" align={align}>
                <Command shouldFilter={false}>
                    <CommandInput
                        placeholder="Search variables..."
                        value={query}
                        onValueChange={setQuery}
                    />
                    <CommandList className="max-h-80">
                        {totalFiltered === 0 ? (
                            <CommandEmpty>No variables found.</CommandEmpty>
                        ) : (
                            filteredGroups.map((group) => (
                                <CommandGroup key={group.category} heading={group.category}>
                                    {group.items.map((variable) => (
                                        <CommandItem
                                            key={variable.name}
                                            value={`${variable.name} ${variable.description} ${variable.category}`}
                                            onSelect={() => {
                                                onSelect(variable)
                                                setOpen(false)
                                                setQuery("")
                                            }}
                                        >
                                            <div className="flex flex-col gap-0.5">
                                                <span className="font-mono text-xs">{`{{${variable.name}}}`}</span>
                                                <span className="text-xs text-muted-foreground">
                                                    {variable.description}
                                                </span>
                                            </div>
                                            <div className="ml-auto flex items-center gap-1">
                                                {variable.required && (
                                                    <Badge variant="secondary" className="text-[10px]">
                                                        Required
                                                    </Badge>
                                                )}
                                                {variable.html_safe && (
                                                    <Badge variant="secondary" className="text-[10px]">
                                                        HTML
                                                    </Badge>
                                                )}
                                            </div>
                                            <CommandShortcut className="hidden" />
                                        </CommandItem>
                                    ))}
                                </CommandGroup>
                            ))
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    )
}

