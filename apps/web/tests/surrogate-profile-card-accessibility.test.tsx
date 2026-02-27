import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { FieldRow } from "@/components/surrogates/profile/ProfileCard/FieldRow"
import type { FormSchema } from "@/lib/api/forms"

// Mock contexts
const mockSetEditingField = vi.fn()
const mockSetFieldValue = vi.fn()
const mockCancelFieldEdit = vi.fn()
const mockToggleHidden = vi.fn()
const mockToggleReveal = vi.fn()

vi.mock("@/components/surrogates/profile/ProfileCard/context", () => ({
    useProfileCardMode: () => ({
        mode: { type: "view", editingField: null },
        setEditingField: mockSetEditingField,
    }),
    useProfileCardEdits: () => ({
        editedFields: {},
        setFieldValue: mockSetFieldValue,
        cancelFieldEdit: mockCancelFieldEdit,
        hiddenFields: [],
        toggleHidden: mockToggleHidden,
        revealedFields: new Set(),
        toggleReveal: mockToggleReveal,
        stagedChanges: [],
    }),
}))

describe("FieldRow accessibility", () => {
    const mockField = {
        key: "test_field",
        label: "Test Label",
        type: "text",
    } as FormSchema["pages"][number]["fields"][number]

    it("renders edit button with aria-label in edit mode", () => {
        // Override mock for edit mode
        vi.mock("@/components/surrogates/profile/ProfileCard/context", () => ({
            useProfileCardMode: () => ({
                mode: { type: "edit", editingField: null },
                setEditingField: mockSetEditingField,
            }),
            useProfileCardEdits: () => ({
                editedFields: {},
                setFieldValue: mockSetFieldValue,
                cancelFieldEdit: mockCancelFieldEdit,
                hiddenFields: [],
                toggleHidden: mockToggleHidden,
                revealedFields: new Set(),
                toggleReveal: mockToggleReveal,
                stagedChanges: [],
            }),
        }))

        render(
            <FieldRow
                fieldKey="test_field"
                field={mockField}
                mergedValue="Value"
                baseValue="Value"
            />
        )

        const editButton = screen.getByRole("button", { name: "Edit Test Label" })
        expect(editButton).toBeInTheDocument()
        fireEvent.click(editButton)
        expect(mockSetEditingField).toHaveBeenCalledWith("test_field")
    })
})
