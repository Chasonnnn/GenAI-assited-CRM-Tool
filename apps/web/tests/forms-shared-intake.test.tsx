import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import PublicIntakeFormClient from '../app/intake/[slug]/page.client'

const {
    getSharedPublicForm,
    getSharedPublicFormDraft,
    lookupSharedPublicFormDraft,
    restoreSharedPublicFormDraft,
    saveSharedPublicFormDraft,
    submitSharedPublicForm,
} = vi.hoisted(() => ({
    getSharedPublicForm: vi.fn(),
    getSharedPublicFormDraft: vi.fn(),
    lookupSharedPublicFormDraft: vi.fn(),
    restoreSharedPublicFormDraft: vi.fn(),
    saveSharedPublicFormDraft: vi.fn(),
    submitSharedPublicForm: vi.fn(),
}))

vi.mock('next/image', () => ({
    default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) =>
        React.createElement('img', { alt, ...props }),
}))

vi.mock('@/lib/api/forms', async () => {
    const actual = await vi.importActual<typeof import('@/lib/api/forms')>('@/lib/api/forms')
    return {
        ...actual,
        getSharedPublicForm,
        getSharedPublicFormDraft,
        lookupSharedPublicFormDraft,
        restoreSharedPublicFormDraft,
        saveSharedPublicFormDraft,
        submitSharedPublicForm,
    }
})

vi.mock('sonner', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
    },
}))

const baseForm = {
    form_id: 'form-1',
    intake_link_id: 'link-1',
    name: 'Shared Intake',
    description: 'Event application form',
    form_schema: {
        pages: [],
        public_title: 'Event Intake Form',
        privacy_notice: 'https://example.com/privacy',
    },
    max_file_size_bytes: 10 * 1024 * 1024,
    max_file_count: 10,
    allowed_mime_types: ['text/plain'],
    campaign_name: 'Spring Event',
    event_name: 'Austin Expo',
}

describe('Shared Intake Public Page', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
        document.documentElement.classList.remove('dark')
        getSharedPublicForm.mockResolvedValue(baseForm)
        getSharedPublicFormDraft.mockResolvedValue({
            answers: {},
            started_at: null,
            updated_at: new Date().toISOString(),
        })
        lookupSharedPublicFormDraft.mockResolvedValue({
            status: "insufficient_identity",
        })
        restoreSharedPublicFormDraft.mockResolvedValue({
            answers: {},
            started_at: null,
            updated_at: new Date().toISOString(),
        })
        saveSharedPublicFormDraft.mockResolvedValue({
            started_at: null,
            updated_at: new Date().toISOString(),
        })
        submitSharedPublicForm.mockResolvedValue({
            id: 'submission-1',
            status: 'pending_review',
            outcome: 'lead_created',
            surrogate_id: null,
            intake_lead_id: 'lead-1',
        })
    })

    it('loads shared intake schema without probing a brand-new draft session', async () => {
        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(getSharedPublicForm).toHaveBeenCalledWith('event-abc')
        expect(getSharedPublicFormDraft).not.toHaveBeenCalled()
    })

    it('does not persist an empty draft session before answers are saved', async () => {
        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(window.localStorage.getItem('intake-draft-session:event-abc')).toBeNull()
    })

    it('restores a saved draft when a draft session already exists', async () => {
        window.localStorage.setItem('intake-draft-session:event-abc', 'saved-session-1')

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(getSharedPublicFormDraft).toHaveBeenCalledWith('event-abc', expect.any(String))
    })

    it('renders a light-surface form shell in dark theme', async () => {
        document.documentElement.classList.add('dark')
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()

        const field = screen.getByLabelText(/full name/i)
        const shell = field.closest('.public-form-light')

        expect(shell).toBeInTheDocument()
        expect(shell).toHaveClass('text-stone-900')
    })

    it('renders the configured public logo in the hosted intake header', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                logo_url: 'https://cdn.example.com/ewi-logo.png',
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        const logo = await screen.findByRole('img', { name: 'Event Intake Form logo' })
        expect(logo).toHaveAttribute('src', 'https://cdn.example.com/ewi-logo.png')
        expect(screen.queryByText('E')).not.toBeInTheDocument()
    })

    it('renders the first intake step as active progress', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                        ],
                    },
                    {
                        title: 'Medical & Preferences',
                        fields: [
                            { key: 'height', label: 'Height', type: 'height', required: false },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(screen.getByRole('progressbar', { name: /application progress/i })).toHaveAttribute(
            'aria-valuenow',
            '33',
        )
    })

    it('treats unsaved uploads as an informational note', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                            { key: 'documents', label: 'Documents', type: 'file', required: false },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        const uploadNote = await screen.findByText("Uploads aren't saved yet")
        expect(uploadNote.closest('[data-slot="public-upload-note"]')).toHaveClass('border-sky-200')
    })

    it('uses example placeholders instead of repeating field labels', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                            { key: 'phone', label: 'Phone', type: 'phone', required: true },
                            { key: 'email', label: 'Email', type: 'email', required: true },
                            { key: 'weight', label: 'Weight', type: 'number', required: false },
                            { key: 'height', label: 'Height', type: 'height', required: false },
                            { key: 'notes', label: 'Notes', type: 'textarea', required: false },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(screen.getByPlaceholderText('e.g. Jane Smith')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('e.g. (555) 123-4567')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('e.g. jane@example.com')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('e.g. 150 lb')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('Share any relevant details')).toBeInTheDocument()
        expect(screen.getByRole('option', { name: 'e.g. 5 ft' })).toBeInTheDocument()
        expect(screen.getByRole('option', { name: 'e.g. 6 in' })).toBeInTheDocument()
        expect(screen.queryByPlaceholderText('Full Name')).not.toBeInTheDocument()
        expect(screen.queryByPlaceholderText('Phone')).not.toBeInTheDocument()
        expect(screen.queryByPlaceholderText('Email')).not.toBeInTheDocument()
        expect(screen.queryByPlaceholderText('Weight')).not.toBeInTheDocument()
    })

    it('submits shared intake and shows lead-created success state', async () => {
        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })

        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        await waitFor(() => {
            expect(submitSharedPublicForm).toHaveBeenCalledWith(
                'event-abc',
                {},
                [],
                undefined,
            )
        })

        expect(
            await screen.findByText(/added to intake review/i),
        ).toBeInTheDocument()
    })

    it('submits visible upload fields with aligned files and field keys', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Uploads',
                        fields: [
                            {
                                key: 'identity_upload',
                                label: 'Identity Document',
                                type: 'file',
                                required: false,
                            },
                            {
                                key: 'insurance_upload',
                                label: 'Insurance Document',
                                type: 'file',
                                required: false,
                            },
                        ],
                    },
                ],
            },
        })
        const identityFile = new File(['identity'], 'identity.txt', { type: 'text/plain' })
        const insuranceFile = new File(['insurance'], 'insurance.txt', { type: 'text/plain' })

        const { container } = render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })
        const fileInputs = Array.from(container.querySelectorAll('input[type="file"]'))
        expect(fileInputs).toHaveLength(2)
        fireEvent.change(fileInputs[0] as HTMLInputElement, {
            target: { files: [identityFile] },
        })
        fireEvent.change(fileInputs[1] as HTMLInputElement, {
            target: { files: [insuranceFile] },
        })

        fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        await waitFor(() => {
            expect(submitSharedPublicForm).toHaveBeenCalledWith(
                'event-abc',
                {},
                [identityFile, insuranceFile],
                ['identity_upload', 'insurance_upload'],
            )
        })
    })

    it('clears the local draft session after successful submit', async () => {
        window.localStorage.setItem('intake-draft-session:event-abc', 'saved-session-1')

        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })
        await waitFor(() =>
            expect(getSharedPublicFormDraft).toHaveBeenCalledWith('event-abc', 'saved-session-1'),
        )

        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        await waitFor(() => {
            expect(submitSharedPublicForm).toHaveBeenCalled()
        })
        expect(window.localStorage.getItem('intake-draft-session:event-abc')).toBeNull()
    })

    it('shows resume prompt and restores previous draft when continuing', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                pages: [
                    {
                        title: 'Identity',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                            { key: 'date_of_birth', label: 'DOB', type: 'text', required: true },
                            { key: 'email', label: 'Email', type: 'email', required: true },
                        ],
                    },
                ],
                public_title: 'Event Intake Form',
                privacy_notice: 'https://example.com/privacy',
            },
        })
        lookupSharedPublicFormDraft.mockResolvedValue({
            status: 'match_found',
            source_draft_id: 'source-draft-1',
            updated_at: new Date().toISOString(),
            match_reason: 'name_dob_email',
        })
        restoreSharedPublicFormDraft.mockResolvedValue({
            answers: {
                full_name: 'Resume Person',
                date_of_birth: '1992-08-09',
                email: 'resume@example.com',
            },
            started_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        })

        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'Resume Person' },
        })
        fireEvent.change(screen.getByLabelText(/dob/i), {
            target: { value: '1992-08-09' },
        })
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'resume@example.com' },
        })

        expect(
            await screen.findByRole('button', { name: /^continue previous application$/i }),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: /^continue previous application$/i }))

        await waitFor(() =>
            expect(restoreSharedPublicFormDraft).toHaveBeenCalledWith(
                'event-abc',
                expect.any(String),
                'source-draft-1',
            ),
        )
        expect(await screen.findByText(/restored saved progress/i)).toBeInTheDocument()
    })

    it('suppresses repeated resume prompt after selecting start new', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                pages: [
                    {
                        title: 'Identity',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                            { key: 'date_of_birth', label: 'DOB', type: 'text', required: true },
                            { key: 'email', label: 'Email', type: 'email', required: true },
                        ],
                    },
                ],
                public_title: 'Event Intake Form',
                privacy_notice: 'https://example.com/privacy',
            },
        })
        lookupSharedPublicFormDraft.mockResolvedValue({
            status: 'match_found',
            source_draft_id: 'source-draft-2',
            updated_at: new Date().toISOString(),
            match_reason: 'name_dob_email',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'Resume Person' },
        })
        fireEvent.change(screen.getByLabelText(/dob/i), {
            target: { value: '1992-08-09' },
        })
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'resume@example.com' },
        })

        expect(
            await screen.findByRole('button', { name: /^continue previous application$/i }),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: /start new/i }))

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'Resume Person ' },
        })

        await new Promise((resolve) => setTimeout(resolve, 900))
        expect(
            screen.queryByRole('button', { name: /^continue previous application$/i }),
        ).not.toBeInTheDocument()
    })
})
