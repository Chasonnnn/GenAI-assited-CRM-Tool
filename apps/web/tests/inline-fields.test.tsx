import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { InlineEditField } from '@/components/inline-edit-field'
import { InlineDateField } from '@/components/inline-date-field'

describe('Inline Fields Accessibility', () => {
    describe('InlineEditField', () => {
        it('renders Save and Cancel buttons with aria-labels when editing', async () => {
            const onSave = vi.fn()
            render(<InlineEditField value="test value" onSave={onSave} label="Email" />)

            // Click to edit
            const trigger = screen.getByText('test value')
            fireEvent.click(trigger)

            // Check for input
            const input = screen.getByLabelText('Email')
            expect(input).toBeInTheDocument()

            // Check for Save button
            const saveButton = screen.getByLabelText('Save Email')
            expect(saveButton).toBeInTheDocument()

            // Check for Cancel button
            const cancelButton = screen.getByLabelText('Cancel Email')
            expect(cancelButton).toBeInTheDocument()
        })

        it('renders default aria-labels if no label prop provided', async () => {
            const onSave = vi.fn()
            render(<InlineEditField value="test value" onSave={onSave} />)

            // Click to edit
            const trigger = screen.getByText('test value')
            fireEvent.click(trigger)

            // Check for Save button
            const saveButton = screen.getByLabelText('Save')
            expect(saveButton).toBeInTheDocument()

            // Check for Cancel button
            const cancelButton = screen.getByLabelText('Cancel')
            expect(cancelButton).toBeInTheDocument()
        })
    })

    describe('InlineDateField', () => {
        it('renders Save and Cancel buttons with aria-labels when editing', async () => {
            const onSave = vi.fn()
            render(<InlineDateField value="2023-01-01" onSave={onSave} label="Start Date" />)

            // Click to edit
            // InlineDateField formats the date. "2023-01-01" -> "Jan 1, 2023"
            const trigger = screen.getByText('Jan 1, 2023')
            fireEvent.click(trigger)

            // Check for input
            const input = screen.getByLabelText('Start Date')
            expect(input).toBeInTheDocument()

            // Check for Save button
            const saveButton = screen.getByLabelText('Save Start Date')
            expect(saveButton).toBeInTheDocument()

            // Check for Cancel button
            const cancelButton = screen.getByLabelText('Cancel Start Date')
            expect(cancelButton).toBeInTheDocument()
        })
    })
})
