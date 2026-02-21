import { render, screen, fireEvent } from '@testing-library/react'
import { InlineEditField } from '@/components/inline-edit-field'
import { describe, it, expect } from 'vitest'

describe('InlineEditField', () => {
    it('renders with value and aria-label', () => {
        render(
            <InlineEditField
                value="Initial Value"
                onSave={async () => {}}
                label="Test Field"
            />
        )

        const button = screen.getByRole('button', { name: /Edit Test Field/i })
        expect(button).toBeInTheDocument()
        expect(screen.getByText('Initial Value')).toBeInTheDocument()
    })

    it('activates edit mode on click', () => {
        render(
            <InlineEditField
                value="Initial Value"
                onSave={async () => {}}
                label="Test Field"
            />
        )

        const button = screen.getByRole('button', { name: /Edit Test Field/i })
        fireEvent.click(button)

        expect(screen.getByRole('textbox', { name: /Test Field/i })).toBeInTheDocument()
    })

    it('activates edit mode on Enter key', () => {
        render(
            <InlineEditField
                value="Initial Value"
                onSave={async () => {}}
                label="Test Field"
            />
        )

        const button = screen.getByRole('button', { name: /Edit Test Field/i })
        button.focus()
        fireEvent.keyDown(button, { key: 'Enter', code: 'Enter' })

        expect(screen.getByRole('textbox', { name: /Test Field/i })).toBeInTheDocument()
    })

    it('activates edit mode on Space key', () => {
        render(
            <InlineEditField
                value="Initial Value"
                onSave={async () => {}}
                label="Test Field"
            />
        )

        const button = screen.getByRole('button', { name: /Edit Test Field/i })
        button.focus()
        fireEvent.keyDown(button, { key: ' ', code: 'Space' })

        expect(screen.getByRole('textbox', { name: /Test Field/i })).toBeInTheDocument()
    })

    it('has accessible focus styles', () => {
        const { container } = render(
            <InlineEditField
                value="Initial Value"
                onSave={async () => {}}
                label="Test Field"
            />
        )

        // This test checks for class names since we can't easily test visual rendering in JSDOM
        const buttonDiv = container.firstChild as HTMLElement
        // We expect focus-visible ring classes and group-focus-visible support for the icon
        // Currently expected to FAIL or be missing these classes
        expect(buttonDiv.className).toContain('focus-visible:ring-2')
    })

    it('shows edit icon on focus', () => {
        const { container } = render(
            <InlineEditField
                value="Initial Value"
                onSave={async () => {}}
                label="Test Field"
            />
        )

        const icon = container.querySelector('svg.lucide-pencil')
        // We expect group-focus-visible:opacity-100 or group-focus:opacity-100
        // SVG className is an object in some environments, so we use getAttribute('class')
        expect(icon?.getAttribute('class')).toMatch(/group-focus(-visible)?:opacity-100/)
    })
})
