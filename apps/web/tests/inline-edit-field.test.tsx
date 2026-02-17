import { render, screen, fireEvent } from "@testing-library/react"
import { InlineEditField } from "@/components/inline-edit-field"
import { describe, it, expect, vi } from "vitest"

describe("InlineEditField", () => {
  it("renders with proper accessibility labels", () => {
    const handleSave = vi.fn()
    render(
      <InlineEditField
        value="Test Value"
        onSave={handleSave}
        label="Test Field"
        placeholder="Enter test value"
      />
    )

    // Check trigger button accessibility
    // We look for a button that contains the text "Test Value" or has the role button
    // The component renders a div with role="button"
    const trigger = screen.getByRole("button", { name: "Edit Test Field" })
    expect(trigger).toBeInTheDocument()

    // Enter edit mode
    fireEvent.click(trigger)

    // Check save and cancel buttons
    // These should fail until we add aria-labels
    const saveButton = screen.getByRole("button", { name: "Save Test Field" })
    const cancelButton = screen.getByRole("button", { name: "Cancel" })

    expect(saveButton).toBeInTheDocument()
    expect(cancelButton).toBeInTheDocument()
  })

  it("uses placeholder as fallback label", () => {
    const handleSave = vi.fn()
    render(
      <InlineEditField
        value="Test Value"
        onSave={handleSave}
        placeholder="Fallback Label"
      />
    )

    const trigger = screen.getByRole("button", { name: "Edit Fallback Label" })
    expect(trigger).toBeInTheDocument()
  })
})
