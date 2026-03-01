import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import PublicApplicationForm from '../app/apply/[token]/page.client'

const {
    savePublicFormDraft,
    submitPublicForm,
    deletePublicFormDraft,
} = vi.hoisted(() => ({
    savePublicFormDraft: vi.fn(),
    submitPublicForm: vi.fn(),
    deletePublicFormDraft: vi.fn(),
}))

vi.mock('next/image', () => ({
    default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => <img alt={alt} {...props} />,
}))

vi.mock('@/lib/api/forms', async () => {
    const actual = await vi.importActual<typeof import('@/lib/api/forms')>('@/lib/api/forms')
    return {
        ...actual,
        savePublicFormDraft,
        submitPublicForm,
        deletePublicFormDraft,
    }
})

describe('Dedicated Apply Page Retirement', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
    })

    it('shows retired-link error for non-preview tokens', async () => {
        render(<PublicApplicationForm token="legacy-token" previewKey="" />)

        expect(await screen.findByRole('heading', { name: /form not available/i })).toBeInTheDocument()
        expect(
            screen.getByText(/dedicated application links have been retired/i),
        ).toBeInTheDocument()
    })

    it('keeps preview mode working when token is preview', async () => {
        window.localStorage.setItem(
            'form-preview:preview-form',
            JSON.stringify({
                form_id: 'form-preview-1',
                name: 'Preview Form',
                description: 'Preview only',
                form_schema: {
                    pages: [],
                    public_title: 'Preview Intake',
                    privacy_notice: 'https://example.com/privacy',
                },
                max_file_size_bytes: 5 * 1024 * 1024,
                max_file_count: 5,
                allowed_mime_types: ['application/pdf'],
            }),
        )

        render(<PublicApplicationForm token="preview" previewKey="preview-form" />)

        expect(await screen.findByRole('heading', { name: 'Preview Intake' })).toBeInTheDocument()
        expect(screen.getByText(/preview mode/i)).toBeInTheDocument()
    })
})
