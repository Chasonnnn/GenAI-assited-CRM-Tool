"use client"

import { useCallback, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import type { BuilderPaletteField } from "@/lib/forms/form-builder-library"
import {
    FALLBACK_FORM_PAGE,
    buildFieldId,
    buildColumnId,
    createBuilderField,
    normalizeValidation,
    type BuilderFormField,
    type BuilderFormPage,
} from "@/lib/forms/form-builder-document"
import type { FormFieldValidation } from "@/lib/api/forms"

const buildOptionKey = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID()
    }
    return `option-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const cloneFieldForDuplicate = (field: BuilderFormField): BuilderFormField => ({
    ...field,
    id: buildFieldId(),
    surrogateFieldMapping: "",
})

const clonePageFields = (fields: BuilderFormField[]) => fields.map(cloneFieldForDuplicate)

export function useFormBuilderDocument(initialPages: BuilderFormPage[] = [FALLBACK_FORM_PAGE]) {
    const [pages, setPages] = useState<BuilderFormPage[]>(initialPages)
    const [activePage, setActivePage] = useState(initialPages[0]?.id ?? FALLBACK_FORM_PAGE.id)
    const [selectedField, setSelectedField] = useState<string | null>(null)
    const [draggedField, setDraggedField] = useState<BuilderPaletteField | null>(null)
    const [draggedFieldId, setDraggedFieldId] = useState<string | null>(null)
    const [dropIndicatorId, setDropIndicatorId] = useState<string | "end" | null>(null)
    const optionKeyMapRef = useRef<Record<string, string[]>>({})

    const currentPage = useMemo(
        () => pages.find((page) => page.id === activePage) ?? pages[0] ?? FALLBACK_FORM_PAGE,
        [pages, activePage],
    )
    const selectedFieldData = useMemo(
        () => (selectedField ? currentPage.fields.find((field) => field.id === selectedField) ?? null : null),
        [currentPage.fields, selectedField],
    )
    const isDragging = Boolean(draggedField || draggedFieldId)

    const selectField = useCallback((fieldId: string | null) => {
        setSelectedField(fieldId)
    }, [])

    const resetDragState = useCallback(() => {
        setDraggedField(null)
        setDraggedFieldId(null)
        setDropIndicatorId(null)
    }, [])

    const resetDocument = useCallback((nextPages: BuilderFormPage[] = [FALLBACK_FORM_PAGE]) => {
        setPages(nextPages.length > 0 ? nextPages : [FALLBACK_FORM_PAGE])
        setActivePage(nextPages[0]?.id ?? FALLBACK_FORM_PAGE.id)
        setSelectedField(null)
        optionKeyMapRef.current = {}
        resetDragState()
    }, [resetDragState])

    const syncOptionKeys = useCallback((fieldId: string, optionCount: number) => {
        const existing = optionKeyMapRef.current[fieldId] ?? []
        if (existing.length === optionCount) {
            return existing
        }
        if (existing.length > optionCount) {
            const next = existing.slice(0, optionCount)
            optionKeyMapRef.current[fieldId] = next
            return next
        }
        const next = [...existing]
        while (next.length < optionCount) {
            next.push(buildOptionKey())
        }
        optionKeyMapRef.current[fieldId] = next
        return next
    }, [])

    const appendOptionKey = useCallback((fieldId: string) => {
        const existing = optionKeyMapRef.current[fieldId] ?? []
        optionKeyMapRef.current[fieldId] = [...existing, buildOptionKey()]
    }, [])

    const removeOptionKey = useCallback((fieldId: string, optionIndex: number) => {
        const existing = optionKeyMapRef.current[fieldId] ?? []
        optionKeyMapRef.current[fieldId] = existing.filter((_, index) => index !== optionIndex)
    }, [])

    const handleDragStart = useCallback((field: BuilderPaletteField) => {
        setDraggedField(field)
        setDraggedFieldId(null)
    }, [])

    const handleFieldDragStart = useCallback((fieldId: string) => {
        setDraggedFieldId(fieldId)
        setDraggedField(null)
    }, [])

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
    }, [])

    const handleCanvasDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        if (!draggedField && !draggedFieldId) return
        if (currentPage.fields.length > 0) {
            setDropIndicatorId("end")
        }
    }, [currentPage.fields.length, draggedField, draggedFieldId])

    const handleFieldDragOver = useCallback((e: React.DragEvent, fieldId: string) => {
        e.preventDefault()
        e.stopPropagation()
        if (!draggedField && !draggedFieldId) return
        setDropIndicatorId(fieldId)
    }, [draggedField, draggedFieldId])

    const moveFieldToIndex = useCallback((fields: BuilderFormField[], fieldId: string, targetIndex: number) => {
        const fromIndex = fields.findIndex((field) => field.id === fieldId)
        if (fromIndex === -1 || fromIndex === targetIndex) return fields

        const nextFields = [...fields]
        const [moved] = nextFields.splice(fromIndex, 1)
        if (!moved) return fields
        const adjustedIndex = fromIndex < targetIndex ? targetIndex - 1 : targetIndex
        const clampedIndex = Math.max(0, Math.min(adjustedIndex, nextFields.length))
        nextFields.splice(clampedIndex, 0, moved)
        return nextFields
    }, [])

    const insertFieldAtIndex = useCallback((fields: BuilderFormField[], field: BuilderFormField, targetIndex: number) => {
        const nextFields = [...fields]
        const clampedIndex = Math.max(0, Math.min(targetIndex, nextFields.length))
        nextFields.splice(clampedIndex, 0, field)
        return nextFields
    }, [])

    const buildNewField = useCallback(() => {
        if (!draggedField) return null
        return createBuilderField(draggedField)
    }, [draggedField])

    const handleInsertField = useCallback((field: BuilderPaletteField) => {
        const newField = createBuilderField(field)
        setPages((prev) =>
            prev.map((page) =>
                page.id === activePage ? { ...page, fields: [...page.fields, newField] } : page,
            ),
        )
        resetDragState()
        selectField(newField.id)
    }, [activePage, resetDragState, selectField])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        const newField = buildNewField()
        const nextSelectedField = newField?.id || draggedFieldId

        setPages((prev) =>
            prev.map((page) => {
                if (page.id !== activePage) return page
                if (draggedFieldId) {
                    return { ...page, fields: moveFieldToIndex(page.fields, draggedFieldId, page.fields.length) }
                }
                if (newField) {
                    return { ...page, fields: [...page.fields, newField] }
                }
                return page
            }),
        )
        resetDragState()
        if (nextSelectedField) {
            selectField(nextSelectedField)
        }
    }, [activePage, buildNewField, draggedFieldId, moveFieldToIndex, resetDragState, selectField])

    const handleDropOnField = useCallback((e: React.DragEvent, targetFieldId: string) => {
        e.preventDefault()
        e.stopPropagation()
        const newField = buildNewField()
        const nextSelectedField = newField?.id || draggedFieldId

        setPages((prev) =>
            prev.map((page) => {
                if (page.id !== activePage) return page
                const targetIndex = page.fields.findIndex((field) => field.id === targetFieldId)
                if (targetIndex === -1) return page
                if (draggedFieldId) {
                    if (draggedFieldId === targetFieldId) return page
                    return { ...page, fields: moveFieldToIndex(page.fields, draggedFieldId, targetIndex) }
                }
                if (newField) {
                    return { ...page, fields: insertFieldAtIndex(page.fields, newField, targetIndex) }
                }
                return page
            }),
        )
        resetDragState()
        if (nextSelectedField) {
            selectField(nextSelectedField)
        }
    }, [activePage, buildNewField, draggedFieldId, insertFieldAtIndex, moveFieldToIndex, resetDragState, selectField])

    const handleDeleteField = useCallback((fieldId: string) => {
        delete optionKeyMapRef.current[fieldId]
        setPages((prev) =>
            prev.map((page) =>
                page.id === activePage ? { ...page, fields: page.fields.filter((field) => field.id !== fieldId) } : page,
            ),
        )
        if (selectedField === fieldId) {
            selectField(null)
        }
    }, [activePage, selectedField, selectField])

    const handleDuplicateField = useCallback((fieldId: string) => {
        const nextId = buildFieldId()
        setPages((prev) =>
            prev.map((page) => {
                if (page.id !== activePage) return page
                const index = page.fields.findIndex((field) => field.id === fieldId)
                if (index === -1) return page
                const source = page.fields[index]
                if (!source) return page
                const duplicated: BuilderFormField = {
                    ...source,
                    id: nextId,
                    label: `${source.label} (Copy)`,
                    surrogateFieldMapping: "",
                }
                const nextFields = [...page.fields]
                nextFields.splice(index + 1, 0, duplicated)
                return { ...page, fields: nextFields }
            }),
        )
        selectField(nextId)
    }, [activePage, selectField])

    const handleUpdateField = useCallback((fieldId: string, updates: Partial<BuilderFormField>) => {
        setPages((prev) =>
            prev.map((page) =>
                page.id === activePage
                    ? {
                        ...page,
                        fields: page.fields.map((field) => (field.id === fieldId ? { ...field, ...updates } : field)),
                    }
                    : page,
            ),
        )
    }, [activePage])

    const handleValidationChange = useCallback((fieldId: string, updates: Partial<FormFieldValidation>) => {
        const nextValidation = normalizeValidation(selectedFieldData?.validation, updates)
        handleUpdateField(fieldId, { validation: nextValidation })
    }, [handleUpdateField, selectedFieldData?.validation])

    const handleAddColumn = useCallback((fieldId: string) => {
        const existing = selectedFieldData?.columns ?? []
        const nextColumns = [
            ...existing,
            {
                id: buildColumnId(),
                label: `Column ${existing.length + 1}`,
                type: "text" as const,
                required: false,
            },
        ]
        handleUpdateField(fieldId, { columns: nextColumns })
    }, [handleUpdateField, selectedFieldData?.columns])

    const handleUpdateColumn = useCallback((
        fieldId: string,
        columnId: string,
        updates: Partial<NonNullable<BuilderFormField["columns"]>[number]>,
    ) => {
        const existing = selectedFieldData?.columns ?? []
        const nextColumns = existing.map((column) =>
            column.id === columnId ? { ...column, ...updates } : column,
        )
        handleUpdateField(fieldId, { columns: nextColumns })
    }, [handleUpdateField, selectedFieldData?.columns])

    const handleRemoveColumn = useCallback((fieldId: string, columnId: string) => {
        const existing = selectedFieldData?.columns ?? []
        const nextColumns = existing.filter((column) => column.id !== columnId)
        handleUpdateField(fieldId, { columns: nextColumns })
    }, [handleUpdateField, selectedFieldData?.columns])

    const handleShowIfChange = useCallback((
        fieldId: string,
        updates: Partial<NonNullable<BuilderFormField["showIf"]>>,
    ) => {
        const current = selectedFieldData?.showIf ?? {
            fieldKey: "",
            operator: "equals" as const,
            value: "",
        }
        const next = { ...current, ...updates }
        if (!next.fieldKey) {
            handleUpdateField(fieldId, { showIf: null })
            return
        }
        if (["is_empty", "is_not_empty"].includes(next.operator)) {
            handleUpdateField(fieldId, { showIf: { ...next, value: "" } })
            return
        }
        handleUpdateField(fieldId, { showIf: next })
    }, [handleUpdateField, selectedFieldData?.showIf])

    const handleMappingChange = useCallback((fieldId: string, value: string | null) => {
        const nextValue = value && value !== "none" ? value : ""
        if (nextValue) {
            const hasConflict = pages.some((page) =>
                page.fields.some(
                    (field) => field.id !== fieldId && field.surrogateFieldMapping === nextValue,
                ),
            )
            if (hasConflict) {
                toast.error("This surrogate field is already mapped to another form field.")
                return
            }
        }
        handleUpdateField(fieldId, { surrogateFieldMapping: nextValue })
    }, [handleUpdateField, pages])

    const handleAddPage = useCallback(() => {
        setPages((prev) => {
            const nextPageId = Math.max(0, ...prev.map((page) => page.id)) + 1
            const newPage: BuilderFormPage = {
                id: nextPageId,
                name: `Page ${nextPageId}`,
                fields: [],
            }
            setActivePage(newPage.id)
            return [...prev, newPage]
        })
    }, [])

    const handleDuplicatePage = useCallback((pageId: number) => {
        setPages((prev) => {
            const nextPageId = Math.max(0, ...prev.map((page) => page.id)) + 1
            const sourcePage = prev.find((page) => page.id === pageId)
            if (!sourcePage) return prev

            const duplicatedFields = clonePageFields(sourcePage.fields)
            const nextPage: BuilderFormPage = {
                id: nextPageId,
                name: `${sourcePage.name} (Copy)`,
                fields: duplicatedFields,
            }

            setActivePage(nextPageId)
            selectField(duplicatedFields[0]?.id ?? null)
            return [...prev, nextPage]
        })
    }, [selectField])

    const deletePage = useCallback((pageId: number) => {
        setPages((prev) => {
            const nextPages = prev.filter((page) => page.id !== pageId)
            if (nextPages.length === 0) {
                setActivePage(FALLBACK_FORM_PAGE.id)
                selectField(null)
                return [FALLBACK_FORM_PAGE]
            }
            if (pageId === activePage) {
                setActivePage(nextPages[0]?.id ?? FALLBACK_FORM_PAGE.id)
                selectField(null)
            }
            return nextPages
        })
    }, [activePage, selectField])

    const addOption = useCallback((fieldId: string) => {
        appendOptionKey(fieldId)
        const existing = selectedFieldData?.options ?? []
        handleUpdateField(fieldId, {
            options: [...existing, `Option ${existing.length + 1}`],
        })
    }, [appendOptionKey, handleUpdateField, selectedFieldData?.options])

    const removeOption = useCallback((fieldId: string, optionIndex: number) => {
        removeOptionKey(fieldId, optionIndex)
        const existing = selectedFieldData?.options ?? []
        handleUpdateField(fieldId, {
            options: existing.filter((_, index) => index !== optionIndex),
        })
    }, [handleUpdateField, removeOptionKey, selectedFieldData?.options])

    return {
        pages,
        setPages,
        activePage,
        setActivePage,
        currentPage,
        selectedField,
        selectField,
        selectedFieldData,
        dropIndicatorId,
        isDragging,
        resetDocument,
        syncOptionKeys,
        handleDragStart,
        handleFieldDragStart,
        handleDragOver,
        handleCanvasDragOver,
        handleFieldDragOver,
        handleDrop,
        handleDropOnField,
        handleDragEnd: resetDragState,
        handleInsertField,
        handleDeleteField,
        handleDuplicateField,
        handleUpdateField,
        handleValidationChange,
        handleAddColumn,
        handleUpdateColumn,
        handleRemoveColumn,
        handleShowIfChange,
        handleMappingChange,
        handleAddPage,
        handleDuplicatePage,
        deletePage,
        addOption,
        removeOption,
    }
}
