import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
import { InlineEditField } from '@/components/inline-edit-field'
import { InlineDateField } from '@/components/inline-date-field'

describe('InlineEditField Accessibility', () => {
    it('enters edit mode on Space key', () => {
        const onSave = vi.fn()
        render(<InlineEditField value="test value" onSave={onSave} label="Test Field" />)

        const displayButton = screen.getByRole('button', { name: /Edit Test Field/i })

        // Should be in display mode initially
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

        // Press Space
        fireEvent.keyDown(displayButton, { key: ' ' })

        // Should be in edit mode now
        expect(screen.getByRole('textbox')).toBeInTheDocument()
        expect(screen.getByRole('textbox')).toHaveValue('test value')
    })

    it('enters edit mode on Enter key', () => {
        const onSave = vi.fn()
        render(<InlineEditField value="test value" onSave={onSave} label="Test Field" />)

        const displayButton = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.keyDown(displayButton, { key: 'Enter' })

        expect(screen.getByRole('textbox')).toBeInTheDocument()
    })

    it('has aria-hidden on decorative icon', () => {
        const onSave = vi.fn()
        const { container } = render(<InlineEditField value="test value" onSave={onSave} label="Test Field" />)

        const svg = container.querySelector('svg.lucide-pencil')
        expect(svg).toHaveAttribute('aria-hidden', 'true')
    })
})

describe('InlineDateField Accessibility', () => {
    it('enters edit mode on Space key', () => {
        const onSave = vi.fn()
        render(<InlineDateField value="2023-01-01" onSave={onSave} label="Date Field" />)

        // Find the button by its text content since aria-label might be missing
        const displayButton = screen.getByText('Jan 1, 2023').closest('[role="button"]')
        expect(displayButton).toBeInTheDocument()

        // Press Space
        if (displayButton) {
            fireEvent.keyDown(displayButton, { key: ' ' })
        }

        // Should be in edit mode. Input has aria-label="Date Field"
        // Note: type="date" might not be role="textbox", so we query by LabelText
        expect(screen.getByLabelText('Date Field')).toBeInTheDocument()
    })

    it('has accessible name on display button', () => {
        const onSave = vi.fn()
        render(<InlineDateField value="2023-01-01" onSave={onSave} label="Date Field" />)

        const displayButton = screen.getByText('Jan 1, 2023').closest('[role="button"]')
        // We expect it to have an aria-label, e.g. "Edit Date Field" or just "Date Field" or derived from label.
        // Current implementation is missing it.
        // We want to assert that it DOES have it after our fix.
        // For now, this test will likely fail if we assert strict accessibility name.

        // Let's check for specific aria-label we intend to add
        expect(displayButton).toHaveAttribute('aria-label', expect.stringContaining('Edit Date Field')) // Or just "Date Field" depending on what we decide
    })

    it('has aria-hidden on decorative icon', () => {
        const onSave = vi.fn()
        const { container } = render(<InlineDateField value="2023-01-01" onSave={onSave} label="Date Field" />)
        const svg = container.querySelector('svg.lucide-pencil')
        expect(svg).toHaveAttribute('aria-hidden', 'true')
    })
})
