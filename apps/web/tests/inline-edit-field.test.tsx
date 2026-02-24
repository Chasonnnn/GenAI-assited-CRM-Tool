import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { InlineEditField } from '@/components/inline-edit-field'

describe('InlineEditField', () => {
    const mockOnSave = vi.fn()
    const defaultProps = {
        value: 'Initial Value',
        onSave: mockOnSave,
        label: 'Test Field',
    }

    beforeEach(() => {
        mockOnSave.mockReset()
    })

    it('enters edit mode on click', () => {
        render(<InlineEditField {...defaultProps} />)
        const trigger = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.click(trigger)
        expect(screen.getByRole('textbox', { name: /Test Field/i })).toBeInTheDocument()
    })

    it('enters edit mode on Enter key', () => {
        render(<InlineEditField {...defaultProps} />)
        const trigger = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.keyDown(trigger, { key: 'Enter' })
        expect(screen.getByRole('textbox', { name: /Test Field/i })).toBeInTheDocument()
    })

    it('enters edit mode on Space key', () => {
        render(<InlineEditField {...defaultProps} />)
        const trigger = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.keyDown(trigger, { key: ' ' })
        expect(screen.getByRole('textbox', { name: /Test Field/i })).toBeInTheDocument()
    })

    it('does NOT save when tabbing to Cancel button', async () => {
        render(<InlineEditField {...defaultProps} />)

        // Enter edit mode
        const trigger = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.click(trigger)

        const input = screen.getByRole('textbox', { name: /Test Field/i })
        const cancelButton = screen.getByRole('button', { name: /Cancel Test Field/i })

        // Change value so save would happen
        fireEvent.change(input, { target: { value: 'New Value' } })

        // Simulate blur with relatedTarget pointing to cancel button
        // This simulates tabbing to the cancel button
        fireEvent.blur(input, { relatedTarget: cancelButton })

        // Ensure state updates settle
        await waitFor(() => {
             expect(mockOnSave).not.toHaveBeenCalled()
        })
    })

    it('saves when clicking outside (blur with no relatedTarget in component)', async () => {
        render(<InlineEditField {...defaultProps} />)

        // Enter edit mode
        const trigger = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.click(trigger)

        const input = screen.getByRole('textbox', { name: /Test Field/i })

        // Change value
        fireEvent.change(input, { target: { value: 'New Value' } })

        // Simulate blur to outside
        fireEvent.blur(input, { relatedTarget: document.body })

        // Ensure state updates settle
        await waitFor(() => {
             expect(mockOnSave).toHaveBeenCalledWith('New Value')
        })
    })
})
