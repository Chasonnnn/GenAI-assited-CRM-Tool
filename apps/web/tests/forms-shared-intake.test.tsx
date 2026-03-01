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
    deleteSharedPublicFormDraft,
} = vi.hoisted(() => ({
    getSharedPublicForm: vi.fn(),
    getSharedPublicFormDraft: vi.fn(),
    lookupSharedPublicFormDraft: vi.fn(),
    restoreSharedPublicFormDraft: vi.fn(),
    saveSharedPublicFormDraft: vi.fn(),
    submitSharedPublicForm: vi.fn(),
    deleteSharedPublicFormDraft: vi.fn(),
}))

vi.mock('next/image', () => ({
    default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => <img alt={alt} {...props} />,
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
        deleteSharedPublicFormDraft,
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
        deleteSharedPublicFormDraft.mockResolvedValue(undefined)
    })

    it('loads shared intake schema and renders title', async () => {
        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(getSharedPublicForm).toHaveBeenCalledWith('event-abc')
        expect(getSharedPublicFormDraft).toHaveBeenCalledWith('event-abc', expect.any(String))
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
        expect(deleteSharedPublicFormDraft).toHaveBeenCalledWith('event-abc', expect.any(String))
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
