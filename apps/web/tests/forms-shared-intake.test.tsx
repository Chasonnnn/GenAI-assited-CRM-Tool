import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import PublicIntakeFormClient from '../app/intake/[slug]/page.client'

const {
    getSharedPublicForm,
    getSharedPublicFormDraft,
    saveSharedPublicFormDraft,
    submitSharedPublicForm,
    deleteSharedPublicFormDraft,
} = vi.hoisted(() => ({
    getSharedPublicForm: vi.fn(),
    getSharedPublicFormDraft: vi.fn(),
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
})
