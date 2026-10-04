import React from 'react'
import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render as renderWithTestingLibrary, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import PublicIntakeFormClient from '../app/intake/[slug]/page.client'
import { toast } from '@/components/ui/toast'
import { ApiError } from '../lib/api'

vi.unmock('@tanstack/react-query')

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

vi.mock('@/components/ui/toast', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
    },
}))

const baseForm = {
    form_id: 'form-1',
    intake_link_id: 'link-1',
    published_version_id: 'version-1',
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

function render(ui: React.ReactElement) {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    })
    return renderWithTestingLibrary(ui, {
        wrapper: ({ children }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        ),
    })
}

function requiredAt<T>(items: readonly T[], index: number): T {
    const item = items[index]
    if (item === undefined) throw new Error(`Expected item at index ${index}`)
    return item
}

describe('Shared Intake Public Page', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
        window.sessionStorage.clear()
        Object.defineProperty(window, 'scrollTo', {
            configurable: true,
            value: vi.fn(),
        })
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
            outcome: 'received',
        })
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.unstubAllEnvs()
    })

    it('loads shared intake schema without probing a brand-new draft session', async () => {
        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(getSharedPublicForm).toHaveBeenCalledWith('event-abc')
        expect(getSharedPublicFormDraft).not.toHaveBeenCalled()
        expect(window.localStorage.getItem('intake-draft-session:event-abc')).toBeNull()
    })

    it('restores a saved draft when a draft session already exists', async () => {
        window.localStorage.setItem('intake-draft-session:event-abc', 'saved-session-1')
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
        getSharedPublicFormDraft.mockResolvedValue({
            answers: { full_name: 'Saved Applicant' },
            started_at: null,
            updated_at: '2026-07-08T12:00:00.000Z',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        expect(getSharedPublicFormDraft).toHaveBeenCalledWith('event-abc', 'saved-session-1')
        expect(screen.getByLabelText(/full name/i)).toHaveValue('Saved Applicant')
    })

    it('shows a date answer as a readable date on the review step', async () => {
        window.localStorage.setItem('intake-draft-session:event-abc', 'saved-session-1')
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            { key: 'date_of_birth', label: 'Date of Birth', type: 'date', required: false },
                        ],
                    },
                ],
            },
        })
        getSharedPublicFormDraft.mockResolvedValue({
            answers: { date_of_birth: '1995-09-15' },
            started_at: null,
            updated_at: '2026-07-08T12:00:00.000Z',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(await screen.findByRole('button', { name: /continue/i }))

        expect(await screen.findByText('Sep 15, 1995')).toBeInTheDocument()
        expect(screen.queryByText('1995-09-15')).not.toBeInTheDocument()
    })

    it('shows choice answers by their option labels on the review step', async () => {
        window.localStorage.setItem('intake-draft-session:event-abc', 'saved-session-1')
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            {
                                key: 'last_delivery',
                                label: 'Last delivery',
                                type: 'select',
                                required: false,
                                options: [
                                    { label: '0-3 months ago', value: 'months_0_3' },
                                    { label: '4-12 months ago', value: 'months_4_12' },
                                ],
                            },
                            {
                                key: 'delivery_type',
                                label: 'Delivery type',
                                type: 'radio',
                                required: false,
                                options: [
                                    { label: 'Vaginal', value: 'vaginal' },
                                    { label: 'C-section', value: 'c_section' },
                                ],
                            },
                            {
                                key: 'contact_times',
                                label: 'Contact times',
                                type: 'multiselect',
                                required: false,
                                options: [
                                    { label: 'Weekday mornings', value: 'weekday_am' },
                                    { label: 'Weekday evenings', value: 'weekday_pm' },
                                ],
                            },
                        ],
                    },
                ],
            },
        })
        getSharedPublicFormDraft.mockResolvedValue({
            answers: {
                last_delivery: 'months_0_3',
                delivery_type: 'c_section',
                contact_times: ['weekday_am', 'retired_option'],
            },
            started_at: null,
            updated_at: '2026-07-08T12:00:00.000Z',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(await screen.findByRole('button', { name: /continue/i }))

        expect(await screen.findByText('0-3 months ago')).toBeInTheDocument()
        expect(screen.getByText('C-section')).toBeInTheDocument()
        // An answer whose option was removed keeps its stored value.
        expect(screen.getByText('Weekday mornings, retired_option')).toBeInTheDocument()
        expect(screen.queryByText('months_0_3')).not.toBeInTheDocument()
        expect(screen.queryByText('c_section')).not.toBeInTheDocument()
    })

    it('replaces a stale saved draft session before autosaving new answers', async () => {
        window.localStorage.setItem('intake-draft-session:event-abc', 'stale-session-1')
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
        getSharedPublicFormDraft.mockRejectedValue(new ApiError(404, 'Not Found', 'Draft missing'))

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Event Intake Form' })).toBeInTheDocument()
        await waitFor(() =>
            expect(getSharedPublicFormDraft).toHaveBeenCalledWith('event-abc', 'stale-session-1'),
        )
        expect(window.localStorage.getItem('intake-draft-session:event-abc')).toBeNull()

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'New Applicant' },
        })

        await waitFor(() => {
            const autosaveCall = saveSharedPublicFormDraft.mock.calls.find(
                ([slug, sessionId, answers]) =>
                    slug === 'event-abc' &&
                    sessionId !== 'stale-session-1' &&
                    (answers as { full_name?: string }).full_name === 'New Applicant',
            )
            expect(autosaveCall).toBeTruthy()
        }, { timeout: 2500 })
        expect(saveSharedPublicFormDraft).not.toHaveBeenCalledWith(
            'event-abc',
            'stale-session-1',
            expect.anything(),
        )
        expect(window.localStorage.getItem('intake-draft-session:event-abc')).not.toBe('stale-session-1')
    })

    it('loads the next shared intake schema when the slug changes in the same component instance', async () => {
        getSharedPublicForm.mockImplementation(async (slug: string) => ({
            ...baseForm,
            form_id: slug === 'event-def' ? 'form-2' : 'form-1',
            form_schema: {
                ...baseForm.form_schema,
                public_title: slug === 'event-def' ? 'Second Event Intake' : 'First Event Intake',
            },
        }))

        const { rerender } = render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'First Event Intake' })).toBeInTheDocument()

        rerender(<PublicIntakeFormClient slug="event-def" />)

        expect(await screen.findByRole('heading', { name: 'Second Event Intake' })).toBeInTheDocument()
        expect(screen.queryByRole('heading', { name: 'First Event Intake' })).not.toBeInTheDocument()
        expect(getSharedPublicForm).toHaveBeenCalledWith('event-abc')
        expect(getSharedPublicForm).toHaveBeenCalledWith('event-def')
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

    it('shows the agency name with its initials above the title when the agency has no logo', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            agency_name: 'Test Organization',
            agency_logo_url: null,
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        const title = await screen.findByRole('heading', { name: 'Event Intake Form', level: 1 })
        const agencyName = screen.getByText('Test Organization')
        const agencyRow = agencyName.closest('[data-slot="public-form-agency"]')
        expect(agencyRow).toHaveTextContent('TO')
        expect(agencyRow?.compareDocumentPosition(title)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
        expect(screen.queryByRole('img')).not.toBeInTheDocument()
        expect(screen.queryByText('E')).not.toBeInTheDocument()
    })

    it('shows the agency logo from the API when the form has no logo', async () => {
        vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'https://api.example.com')
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            agency_name: 'Sunrise Surrogacy',
            agency_logo_url: '/forms/public/org-1/signature-logo',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        const logo = await screen.findByRole('img', { name: 'Sunrise Surrogacy logo' })
        expect(logo).toHaveAttribute('src', 'https://api.example.com/forms/public/org-1/signature-logo')
        expect(screen.getByText('Sunrise Surrogacy')).toBeInTheDocument()
        expect(screen.queryByText('SS')).not.toBeInTheDocument()
    })

    it('prefers the form logo over the agency logo', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                logo_url: 'https://cdn.example.com/ewi-logo.png',
            },
            agency_name: 'Sunrise Surrogacy',
            agency_logo_url: '/forms/public/org-1/signature-logo',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        const logo = await screen.findByRole('img', { name: 'Sunrise Surrogacy logo' })
        expect(logo).toHaveAttribute('src', 'https://cdn.example.com/ewi-logo.png')
        expect(screen.getAllByRole('img')).toHaveLength(1)
    })

    it('falls back to agency initials when the logo fails to load', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            agency_name: 'Sunrise Surrogacy',
            agency_logo_url: 'https://cdn.example.com/missing.png',
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        fireEvent.error(await screen.findByRole('img', { name: 'Sunrise Surrogacy logo' }))

        expect(await screen.findByText('SS')).toBeInTheDocument()
        expect(screen.queryByRole('img')).not.toBeInTheDocument()
        expect(screen.getByText('Sunrise Surrogacy')).toBeInTheDocument()
    })

    it('wraps a long agency name instead of cutting it to one line', async () => {
        const longName = 'Sunrise Surrogacy & Egg Donation Agency of Southern California, LLC'
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            agency_name: longName,
            agency_logo_url: null,
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form', level: 1 })
        const agencyName = screen.getByText(longName)
        expect(agencyName).not.toHaveClass('truncate')
        expect(agencyName).toHaveClass('line-clamp-2', 'break-words')
    })

    it('keeps the old header when the API sends no agency name', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            agency_name: null,
            agency_logo_url: null,
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form', level: 1 })
        expect(document.querySelector('[data-slot="public-form-agency"]')).toBeNull()
        expect(screen.getByText('E')).toBeInTheDocument()
    })

    it('shows the full name of the current page in the step list', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Medical & Pregnancy History',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                        ],
                    },
                    {
                        title: 'Background & Family Details',
                        fields: [
                            { key: 'height', label: 'Height', type: 'height', required: false },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })
        const currentLabel = screen.getByText('Medical & Pregnancy History')
        expect(currentLabel).not.toHaveClass('truncate')
        expect(currentLabel).toHaveClass('line-clamp-3', 'break-words')
        expect(screen.queryByText('Medical Pregnancy')).not.toBeInTheDocument()
        // Other steps keep their short labels.
        expect(screen.getByText('Background Family')).toBeInTheDocument()
        expect(screen.queryByText('Background & Family Details')).not.toBeInTheDocument()
    })

    it('starts the question card with the first question, not the page name', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Page 1',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                        ],
                    },
                ],
            },
            agency_name: 'Sunrise Surrogacy',
            agency_logo_url: null,
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })
        expect(screen.getAllByText('Page 1')).toHaveLength(1)
        const card = screen.getByLabelText(/full name/i).closest('[data-slot="card"]')
        expect(card).not.toHaveTextContent('Page 1')
        expect(card?.querySelector('[data-slot="card-header"]')).toBeNull()
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
        const progress = screen.getByRole('progressbar', { name: /application progress/i })
        expect(progress.tagName).toBe('PROGRESS')
        expect(progress).toHaveAttribute('value', '33')
        expect(progress).toHaveAttribute('max', '100')
        expect(progress).toHaveClass('[&::-webkit-progress-value]:bg-primary')
        // The page title shows only as its step label.
        expect(screen.getAllByText('Application')).toHaveLength(1)
        expect(screen.getByText('Step 1 of 3')).toBeInTheDocument()
    })

    it('marks every invalid field inline on Continue and focuses the first one', async () => {
        const { toast } = await import('@/components/ui/toast')
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Application',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                            { key: 'email', label: 'Email', type: 'email', required: true },
                            {
                                key: 'smoker',
                                label: 'Do you smoke?',
                                type: 'radio',
                                required: true,
                                options: [
                                    { label: 'Yes', value: 'yes' },
                                    { label: 'No', value: 'no' },
                                ],
                            },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'not-an-email' } })
        fireEvent.click(screen.getByRole('button', { name: /continue/i }))

        const fullName = screen.getByLabelText(/full name/i)
        expect(fullName).toHaveAttribute('aria-invalid', 'true')
        expect(fullName).toHaveAccessibleDescription('Full Name is required.')
        expect(screen.getByLabelText(/email/i)).toHaveAccessibleDescription(
            'Email must be a valid email address.',
        )
        expect(screen.getByRole('radiogroup', { name: /do you smoke/i })).toHaveAccessibleDescription(
            'Do you smoke? is required.',
        )
        await waitFor(() => expect(fullName).toHaveFocus())
        expect(toast.error).not.toHaveBeenCalled()
        expect(screen.queryByRole('button', { name: 'Submit Application' })).not.toBeInTheDocument()

        fireEvent.change(fullName, { target: { value: 'Jane Applicant' } })
        expect(fullName).not.toHaveAttribute('aria-invalid')
        expect(screen.queryByText('Full Name is required.')).not.toBeInTheDocument()
    })

    it('returns to the page with a missing required upload and marks it inline', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Documents',
                        fields: [
                            { key: 'profile_photo', label: 'Profile Photo', type: 'file', required: true },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        fireEvent.click(await screen.findByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        const uploadGroup = await screen.findByRole('group', { name: 'Profile Photo' })
        expect(uploadGroup).toHaveAttribute('aria-invalid', 'true')
        expect(uploadGroup).toHaveAccessibleDescription('Upload Profile Photo.')
        expect(submitSharedPublicForm).not.toHaveBeenCalled()
    })

    it('falls back to the form name when no public title is set', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: { ...baseForm.form_schema, public_title: '' },
        })

        render(<PublicIntakeFormClient slug="event-abc" />)

        expect(await screen.findByRole('heading', { name: 'Shared Intake', level: 1 })).toBeInTheDocument()
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
        expect(screen.getByLabelText(/select files to upload/i)).toHaveAttribute('type', 'file')
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
        expect(screen.getByRole('combobox', { name: 'Height Feet' })).toHaveTextContent('e.g. 5 ft')
        expect(screen.getByRole('combobox', { name: 'Height Inches' })).toHaveTextContent('e.g. 6 in')
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
                undefined,
                undefined,
                'version-1',
                expect.any(String),
                expect.objectContaining({ landing_url: expect.any(String) }),
            )
        })

        expect(
            await screen.findByText(/added to intake review/i),
        ).toBeInTheDocument()
    })

    it('reuses the submission attempt after a lost response and a page remount', async () => {
        submitSharedPublicForm.mockRejectedValueOnce(new Error('Response lost'))
        const firstPage = render(<PublicIntakeFormClient slug="retry-form" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))
        await waitFor(() => {
            expect(submitSharedPublicForm).toHaveBeenCalledTimes(1)
            expect(screen.getByRole('button', { name: 'Submit Application' })).toBeEnabled()
        })
        const attemptKey = submitSharedPublicForm.mock.calls[0]?.[7]
        expect(attemptKey).toEqual(expect.any(String))

        firstPage.unmount()
        render(<PublicIntakeFormClient slug="retry-form" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))
        await screen.findByText(/added to intake review/i)
        expect(submitSharedPublicForm.mock.calls[1]?.[7]).toBe(attemptKey)
        expect(window.sessionStorage.getItem('intake-submit:retry-form:version-1')).toBeNull()
    })

    it('keeps submission attempts isolated by intake link and published version', async () => {
        window.sessionStorage.setItem('intake-submit:other-form:version-1', 'other-attempt')
        window.sessionStorage.setItem('intake-submit:event-abc:old-version', 'old-attempt')
        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))
        await screen.findByText(/added to intake review/i)
        const attemptKey = submitSharedPublicForm.mock.calls[0]?.[7]
        expect(attemptKey).toEqual(expect.any(String))
        expect(attemptKey).not.toBe('other-attempt')
        expect(attemptKey).not.toBe('old-attempt')
        expect(window.sessionStorage.getItem('intake-submit:other-form:version-1')).toBe('other-attempt')
    })

    describe('landing attribution', () => {
        const originalLocation = window.location
        const landingUrl =
            'https://app.surrogacyforce.com/intake/event-abc?utm_source=facebook&utm_campaign=donor-fall&fbclid=click-abc&ad_id=ad-9&email=leak@example.com'

        function setLocation(url: string) {
            const next = new URL(url)
            Object.defineProperty(window, 'location', {
                writable: true,
                value: { ...originalLocation, href: next.href, origin: next.origin, search: next.search },
            })
        }

        async function submitApplication() {
            await screen.findByRole('heading', { name: 'Event Intake Form' })
            fireEvent.click(screen.getByRole('checkbox'))
            fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))
        }

        beforeEach(() => {
            vi.useFakeTimers({ toFake: ['Date'] })
            vi.setSystemTime(new Date('2026-09-27T12:00:00.123Z'))
            Object.defineProperty(document, 'referrer', {
                configurable: true,
                value: 'https://www.ewisurrogacy.com/egg-donors?utm_source=facebook',
            })
        })

        afterEach(() => {
            Object.defineProperty(window, 'location', { writable: true, value: originalLocation })
            Object.defineProperty(document, 'referrer', { configurable: true, value: '' })
        })

        it('sends allowlisted query values, a millisecond fbc, the landing URL and referrer', async () => {
            setLocation(`${landingUrl}#apply`)
            render(<PublicIntakeFormClient slug="event-abc" />)

            await submitApplication()

            await waitFor(() => expect(submitSharedPublicForm).toHaveBeenCalledTimes(1))
            expect(submitSharedPublicForm.mock.calls[0]?.[8]).toEqual({
                utm_source: 'facebook',
                utm_campaign: 'donor-fall',
                fbclid: 'click-abc',
                ad_id: 'ad-9',
                fbc: `fb.1.${Date.parse('2026-09-27T12:00:00.123Z')}.click-abc`,
                referrer: 'https://www.ewisurrogacy.com/egg-donors',
                landing_url: landingUrl,
            })
            await screen.findByText(/added to intake review/i)
            expect(window.localStorage.getItem('intake-attribution:event-abc')).toBeNull()
        })

        it('keeps the first landing attribution through a failed submit and a later bare visit', async () => {
            submitSharedPublicForm.mockRejectedValueOnce(new Error('Response lost'))
            setLocation(landingUrl)
            const firstPage = render(<PublicIntakeFormClient slug="event-abc" />)
            await submitApplication()
            await waitFor(() => {
                expect(submitSharedPublicForm).toHaveBeenCalledTimes(1)
                expect(screen.getByRole('button', { name: 'Submit Application' })).toBeEnabled()
            })
            firstPage.unmount()

            vi.setSystemTime(new Date('2026-09-28T09:30:00.000Z'))
            setLocation('https://app.surrogacyforce.com/intake/event-abc')
            render(<PublicIntakeFormClient slug="event-abc" />)
            await submitApplication()

            await screen.findByText(/added to intake review/i)
            const firstAttribution = submitSharedPublicForm.mock.calls[0]?.[8]
            expect(firstAttribution).toMatchObject({
                fbclid: 'click-abc',
                fbc: `fb.1.${Date.parse('2026-09-27T12:00:00.123Z')}.click-abc`,
            })
            expect(submitSharedPublicForm.mock.calls[1]?.[8]).toEqual(firstAttribution)
        })

        it('replaces stored attribution when a later visit brings new query values', async () => {
            window.localStorage.setItem(
                'intake-attribution:event-abc',
                JSON.stringify({
                    query: { utm_source: 'google' },
                    attribution: { utm_source: 'google', landing_url: 'https://app.surrogacyforce.com/intake/event-abc?utm_source=google' },
                }),
            )
            setLocation('https://app.surrogacyforce.com/intake/event-abc?utm_source=facebook&fbc=fb.1.1790510400000.click-xyz')
            render(<PublicIntakeFormClient slug="event-abc" />)

            await submitApplication()

            await waitFor(() => expect(submitSharedPublicForm).toHaveBeenCalledTimes(1))
            expect(submitSharedPublicForm.mock.calls[0]?.[8]).toMatchObject({
                utm_source: 'facebook',
                fbc: 'fb.1.1790510400000.click-xyz',
            })
        })
    })

    it.each([
        {
            name: 'a stale form version',
            error: new ApiError(409, 'Conflict', 'Published version is no longer current'),
            message: 'This form changed. Reload the page and try again.',
        },
        {
            name: 'a pending duplicate applicant',
            error: new ApiError(409, 'Conflict', 'An intake submission is already pending review.'),
            message: 'Failed to submit application. Please try again.',
        },
        {
            name: 'a conflict without a detail',
            error: new ApiError(409, 'Conflict'),
            message: 'Failed to submit application. Please try again.',
        },
        {
            name: 'a network failure',
            error: new Error('Network down'),
            message: 'Failed to submit application. Please try again.',
        },
    ])('shows the submit failure message for $name', async ({ error, message }) => {
        submitSharedPublicForm.mockRejectedValueOnce(error)
        render(<PublicIntakeFormClient slug="event-abc" />)
        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message))
        expect(toast.error).toHaveBeenCalledTimes(1)
        expect(screen.getByText('Review Your Application')).toBeInTheDocument()
        expect(JSON.stringify(vi.mocked(toast.error).mock.calls)).not.toContain(error.message)
        expect(document.body).not.toHaveTextContent(error.message)
    })

    it('keeps both SMS choices unchecked and optional on hosted intake', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Contact',
                        fields: [{ key: 'mobile_number', label: 'Mobile Phone', type: 'phone', required: false }],
                    },
                ],
            },
            messaging_consent: {
                phone_field_key: 'mobile_number',
                operational: {
                    disclosure: 'I agree to receive application and appointment texts.',
                    sms_terms_url: 'https://example.com/sms-terms',
                    privacy_policy_url: 'https://example.com/privacy',
                },
                promotional: {
                    disclosure: 'I agree to receive promotional opportunity texts.',
                    sms_terms_url: 'https://example.com/sms-terms',
                    privacy_policy_url: 'https://example.com/privacy',
                },
            },
        })
        render(<PublicIntakeFormClient slug="event-abc" />)

        await screen.findByLabelText('Mobile Phone')
        const operational = screen.getByRole('checkbox', {
            name: /application and appointment texts/i,
        })
        const promotional = screen.getByRole('checkbox', {
            name: /promotional opportunity texts/i,
        })
        expect(operational).not.toBeChecked()
        expect(promotional).not.toBeChecked()
        expect(screen.getAllByRole('link', { name: 'Terms of Service' })).toHaveLength(2)

        fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        await screen.findByText('Review Your Application')
        fireEvent.click(screen.getByRole('checkbox', { name: /information provided is accurate/i }))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        await waitFor(() => {
            expect(submitSharedPublicForm).toHaveBeenCalledWith(
                'event-abc',
                {},
                [],
                undefined,
                undefined,
                { operational: false, promotional: false, phoneFieldKey: null },
                'version-1',
                expect.any(String),
                expect.objectContaining({ landing_url: expect.any(String) }),
            )
        })
    })

    describe('SMS consent next to the phone field', () => {
        const fullNameField = { key: 'full_name', label: 'Full Name', type: 'text', required: true }
        const homePhoneField = { key: 'phone', label: 'Home Phone', type: 'phone', required: false }
        const mobilePhoneField = { key: 'mobile_number', label: 'Mobile Phone', type: 'phone', required: false }
        const emailField = { key: 'email', label: 'Email', type: 'email', required: true }
        const smsIntakeForm = {
            ...baseForm,
            form_schema: {
                ...baseForm.form_schema,
                privacy_notice: 'By submitting this form, you consent to intake screening.',
                pages: [
                    {
                        title: 'Contact',
                        fields: [fullNameField, homePhoneField, mobilePhoneField, emailField],
                    },
                ],
            },
            messaging_consent: {
                phone_field_key: 'mobile_number',
                operational: {
                    disclosure: 'I agree to receive application and appointment texts.',
                    sms_terms_url: 'https://example.com/sms-terms',
                    privacy_policy_url: 'https://example.com/privacy',
                },
                promotional: null,
            },
        }
        const missingPhoneMessage = 'Add a phone number to receive text messages, or uncheck to continue.'

        function isBefore(first: HTMLElement, second: HTMLElement): boolean {
            return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
        }

        function fillRequiredContactFields() {
            fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Applicant' } })
            fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'jane@example.com' } })
        }

        function getSmsCheckbox() {
            return screen.getByRole('checkbox', { name: /application and appointment texts/i })
        }

        function querySmsCheckbox() {
            return screen.queryByRole('checkbox', { name: /application and appointment texts/i })
        }

        function submitReviewStep() {
            fireEvent.click(screen.getByRole('checkbox', { name: /information provided is accurate/i }))
            fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))
        }

        it('renders the SMS consent on the phone step directly after the mapped phone field', async () => {
            getSharedPublicForm.mockResolvedValue(smsIntakeForm)
            render(<PublicIntakeFormClient slug="event-abc" />)

            const phoneInput = await screen.findByLabelText('Mobile Phone')
            const smsCheckbox = getSmsCheckbox()
            expect(isBefore(screen.getByLabelText('Home Phone'), phoneInput)).toBe(true)
            expect(isBefore(phoneInput, smsCheckbox)).toBe(true)
            expect(isBefore(smsCheckbox, screen.getByLabelText(/email/i))).toBe(true)
            expect(isBefore(smsCheckbox, screen.getByText(/you consent to intake screening/i))).toBe(true)
            expect(smsCheckbox).not.toBeChecked()

            expect(screen.getByText(/application and appointment texts/i)).toHaveClass('text-sm', 'text-stone-700')
            const termsLink = screen.getByRole('link', { name: 'Terms of Service' })
            expect(termsLink).toHaveAttribute('href', 'https://example.com/sms-terms')
            expect(termsLink).toHaveAttribute('target', '_blank')
            const privacyLinks = screen.getAllByRole('link', { name: 'Privacy Policy' })
            expect(privacyLinks[0]).toHaveAttribute('href', 'https://example.com/privacy')
            expect(privacyLinks[0]).toHaveAttribute('target', '_blank')
            expect(screen.queryByRole('link', { name: 'SMS Terms' })).not.toBeInTheDocument()
        })

        it('renders the SMS consent only on the later step that holds the phone field', async () => {
            getSharedPublicForm.mockResolvedValue({
                ...smsIntakeForm,
                form_schema: {
                    ...smsIntakeForm.form_schema,
                    pages: [
                        { title: 'About You', fields: [fullNameField] },
                        { title: 'Contact', fields: [mobilePhoneField, emailField] },
                    ],
                },
            })
            render(<PublicIntakeFormClient slug="event-abc" />)

            await screen.findByLabelText(/full name/i)
            expect(querySmsCheckbox()).not.toBeInTheDocument()
            fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Applicant' } })
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))

            const phoneInput = await screen.findByLabelText('Mobile Phone')
            const smsCheckbox = getSmsCheckbox()
            expect(isBefore(phoneInput, smsCheckbox)).toBe(true)
            expect(isBefore(smsCheckbox, screen.getByLabelText(/email/i))).toBe(true)

            fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'jane@example.com' } })
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            expect(querySmsCheckbox()).not.toBeInTheDocument()
        })

        it('continues and submits with SMS unchecked and no phone number', async () => {
            getSharedPublicForm.mockResolvedValue(smsIntakeForm)
            render(<PublicIntakeFormClient slug="event-abc" />)
            await screen.findByLabelText('Mobile Phone')

            fillRequiredContactFields()
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            expect(querySmsCheckbox()).not.toBeInTheDocument()
            submitReviewStep()

            await waitFor(() => {
                expect(submitSharedPublicForm).toHaveBeenCalledWith(
                    'event-abc',
                    { full_name: 'Jane Applicant', email: 'jane@example.com' },
                    [],
                    undefined,
                    undefined,
                    { operational: false, promotional: false, phoneFieldKey: null },
                    'version-1',
                    expect.any(String),
                    expect.objectContaining({ landing_url: expect.any(String) }),
                )
            })
        })

        it('shows an inline message and stays on the step when SMS is checked without a phone number', async () => {
            getSharedPublicForm.mockResolvedValue(smsIntakeForm)
            render(<PublicIntakeFormClient slug="event-abc" />)
            await screen.findByLabelText('Mobile Phone')

            fillRequiredContactFields()
            const smsCheckbox = getSmsCheckbox()
            fireEvent.click(smsCheckbox)
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))

            const message = await screen.findByText('Enter your phone number to receive text messages.')
            expect(message).toHaveAttribute('role', 'alert')
            expect(screen.queryByText('Review Your Application')).not.toBeInTheDocument()
            expect(smsCheckbox).toHaveAttribute('aria-invalid', 'true')
            expect(smsCheckbox).toHaveAccessibleDescription(message.textContent ?? '')
            expect(screen.getByLabelText('Mobile Phone')).toHaveFocus()

            fireEvent.change(screen.getByLabelText('Mobile Phone'), { target: { value: '(555) 123-4567' } })
            expect(screen.queryByText('Enter your phone number to receive text messages.')).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            submitReviewStep()

            await waitFor(() => {
                expect(submitSharedPublicForm).toHaveBeenCalledWith(
                    'event-abc',
                    { full_name: 'Jane Applicant', mobile_number: '(555) 123-4567', email: 'jane@example.com' },
                    [],
                    undefined,
                    undefined,
                    { operational: true, promotional: false, phoneFieldKey: 'mobile_number' },
                    'version-1',
                    expect.any(String),
                    expect.objectContaining({ landing_url: expect.any(String) }),
                )
            })
        })

        it('reports a malformed phone inline on the first Continue when SMS is checked', async () => {
            getSharedPublicForm.mockResolvedValue(smsIntakeForm)
            render(<PublicIntakeFormClient slug="event-abc" />)
            await screen.findByLabelText('Mobile Phone')

            fillRequiredContactFields()
            fireEvent.change(screen.getByLabelText('Mobile Phone'), { target: { value: '123' } })
            const smsCheckbox = getSmsCheckbox()
            fireEvent.click(smsCheckbox)
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))

            const message = await screen.findByText('Enter a valid phone number to receive text messages.')
            expect(message).toHaveAttribute('role', 'alert')
            expect(smsCheckbox).toHaveAttribute('aria-invalid', 'true')
            expect(smsCheckbox).toHaveAccessibleDescription(message.textContent ?? '')
            expect(screen.getByLabelText('Mobile Phone')).toHaveFocus()
            expect(toast.error).not.toHaveBeenCalled()
            expect(screen.queryByText('Review Your Application')).not.toBeInTheDocument()
        })

        it('continues after unchecking SMS that blocked an empty phone', async () => {
            getSharedPublicForm.mockResolvedValue(smsIntakeForm)
            render(<PublicIntakeFormClient slug="event-abc" />)
            await screen.findByLabelText('Mobile Phone')

            fillRequiredContactFields()
            fireEvent.click(getSmsCheckbox())
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Enter your phone number to receive text messages.')

            fireEvent.click(getSmsCheckbox())
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
            expect(getSmsCheckbox()).not.toHaveAttribute('aria-invalid')
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            submitReviewStep()

            await waitFor(() => {
                expect(submitSharedPublicForm).toHaveBeenCalledWith(
                    'event-abc',
                    { full_name: 'Jane Applicant', email: 'jane@example.com' },
                    [],
                    undefined,
                    undefined,
                    { operational: false, promotional: false, phoneFieldKey: null },
                    'version-1',
                    expect.any(String),
                    expect.objectContaining({ landing_url: expect.any(String) }),
                )
            })
        })

        it('blocks checked SMS on review after conditional logic hides the phone field until SMS is unchecked', async () => {
            getSharedPublicForm.mockResolvedValue({
                ...smsIntakeForm,
                form_schema: {
                    ...smsIntakeForm.form_schema,
                    pages: [
                        {
                            title: 'Contact',
                            fields: [
                                fullNameField,
                                { key: 'contact_preference', label: 'Contact Preference', type: 'text', required: false },
                                {
                                    ...mobilePhoneField,
                                    show_if: {
                                        field_key: 'contact_preference',
                                        operator: 'not_equals',
                                        value: 'Email only',
                                    },
                                },
                                emailField,
                            ],
                        },
                    ],
                },
            })
            render(<PublicIntakeFormClient slug="event-abc" />)
            await screen.findByLabelText('Mobile Phone')

            fillRequiredContactFields()
            fireEvent.click(getSmsCheckbox())
            fireEvent.change(screen.getByLabelText('Contact Preference'), { target: { value: 'Email only' } })
            expect(screen.queryByLabelText('Mobile Phone')).not.toBeInTheDocument()
            expect(querySmsCheckbox()).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))

            await screen.findByText('Review Your Application')
            const smsCheckbox = getSmsCheckbox()
            expect(smsCheckbox).toBeChecked()
            submitReviewStep()

            const message = await screen.findByText(missingPhoneMessage)
            expect(message).toHaveAttribute('role', 'alert')
            expect(smsCheckbox).toHaveAttribute('aria-invalid', 'true')
            expect(smsCheckbox).toHaveAccessibleDescription(missingPhoneMessage)
            expect(smsCheckbox).toHaveFocus()
            expect(submitSharedPublicForm).not.toHaveBeenCalled()

            fireEvent.click(smsCheckbox)
            expect(screen.queryByText(missingPhoneMessage)).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

            await waitFor(() => {
                expect(submitSharedPublicForm).toHaveBeenCalledWith(
                    'event-abc',
                    { full_name: 'Jane Applicant', contact_preference: 'Email only', email: 'jane@example.com' },
                    [],
                    undefined,
                    undefined,
                    { operational: false, promotional: false, phoneFieldKey: null },
                    'version-1',
                    expect.any(String),
                    expect.objectContaining({ landing_url: expect.any(String) }),
                )
            })
        })

        it('returns to the phone step and focuses the phone when a later answer reveals it after SMS was checked on review', async () => {
            getSharedPublicForm.mockResolvedValue({
                ...smsIntakeForm,
                form_schema: {
                    ...smsIntakeForm.form_schema,
                    pages: [
                        {
                            title: 'Contact',
                            fields: [
                                fullNameField,
                                {
                                    ...mobilePhoneField,
                                    show_if: { field_key: 'contact_preference', operator: 'equals', value: 'Text' },
                                },
                            ],
                        },
                        {
                            title: 'Preferences',
                            fields: [
                                emailField,
                                { key: 'contact_preference', label: 'Contact Preference', type: 'text', required: false },
                            ],
                        },
                    ],
                },
            })
            render(<PublicIntakeFormClient slug="event-abc" />)

            await screen.findByLabelText(/full name/i)
            expect(screen.queryByLabelText('Mobile Phone')).not.toBeInTheDocument()
            fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Jane Applicant' } })
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            fireEvent.change(await screen.findByLabelText(/email/i), { target: { value: 'jane@example.com' } })
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))

            await screen.findByText('Review Your Application')
            fireEvent.click(getSmsCheckbox())
            fireEvent.click(screen.getByRole('checkbox', { name: /information provided is accurate/i }))
            fireEvent.click(requiredAt(screen.getAllByRole('button', { name: /edit/i }), 1))

            fireEvent.change(await screen.findByLabelText('Contact Preference'), { target: { value: 'Text' } })
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            expect(querySmsCheckbox()).not.toBeInTheDocument()
            const submitButton = screen.getByRole('button', { name: 'Submit Application' })
            submitButton.focus()
            fireEvent.click(submitButton)

            const message = await screen.findByText('Enter your phone number to receive text messages.')
            expect(message).toHaveAttribute('role', 'alert')
            expect(screen.queryByText('Review Your Application')).not.toBeInTheDocument()
            expect(getSmsCheckbox()).toHaveAttribute('aria-invalid', 'true')
            expect(screen.getByLabelText('Mobile Phone')).toHaveFocus()
            expect(submitSharedPublicForm).not.toHaveBeenCalled()
        })

        it('sends the mapped phone field key with checked SMS and shows the server message when the form changed', async () => {
            submitSharedPublicForm.mockRejectedValueOnce(
                new ApiError(409, 'Conflict', 'This form changed. Reload the page and try again.'),
            )
            getSharedPublicForm.mockResolvedValue(smsIntakeForm)
            render(<PublicIntakeFormClient slug="event-abc" />)
            await screen.findByLabelText('Mobile Phone')

            fillRequiredContactFields()
            fireEvent.change(screen.getByLabelText('Mobile Phone'), { target: { value: '(555) 123-4567' } })
            fireEvent.click(getSmsCheckbox())
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            submitReviewStep()

            await waitFor(() => {
                expect(toast.error).toHaveBeenCalledWith('This form changed. Reload the page and try again.')
            })
            expect(submitSharedPublicForm).toHaveBeenCalledWith(
                'event-abc',
                { full_name: 'Jane Applicant', mobile_number: '(555) 123-4567', email: 'jane@example.com' },
                [],
                undefined,
                undefined,
                { operational: true, promotional: false, phoneFieldKey: 'mobile_number' },
                'version-1',
                expect.any(String),
                expect.objectContaining({ landing_url: expect.any(String) }),
            )
            expect(screen.getByText('Review Your Application')).toBeInTheDocument()
        })

        it.each([
            {
                name: 'a null phone field key',
                messagingConsent: { phone_field_key: null, operational: null, promotional: null },
            },
            { name: 'missing options', messagingConsent: undefined },
        ])('does not render SMS consent with $name', async ({ messagingConsent }) => {
            getSharedPublicForm.mockResolvedValue({ ...smsIntakeForm, messaging_consent: messagingConsent })
            render(<PublicIntakeFormClient slug="event-abc" />)

            await screen.findByLabelText('Mobile Phone')
            expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
            expect(screen.queryByRole('link', { name: 'Terms of Service' })).not.toBeInTheDocument()

            fillRequiredContactFields()
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
            await screen.findByText('Review Your Application')
            expect(screen.getAllByRole('checkbox')).toHaveLength(1)
        })
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
                undefined,
                undefined,
                'version-1',
                expect.any(String),
                expect.objectContaining({ landing_url: expect.any(String) }),
            )
        })
    })

    it('requires and submits the donor profile image with its mapped field key', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            allowed_mime_types: ['image/png', 'image/jpeg'],
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Donor Application',
                        fields: [
                            { key: 'full_name', label: 'Full Name', type: 'text', required: true },
                            { key: 'email', label: 'Email', type: 'email', required: true },
                            {
                                key: 'profile_photo',
                                label: 'Profile Photo',
                                type: 'file',
                                required: true,
                            },
                        ],
                    },
                ],
            },
        })
        const photo = new File(['photo'], 'profile.jpg', { type: 'image/jpeg' })
        const { container } = render(<PublicIntakeFormClient slug="donor-form" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })
        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'Dana Donor' },
        })
        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'dana@example.com' },
        })
        const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement
        expect(fileInput).toHaveAttribute('accept', 'image/png,image/jpeg')

        fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        expect(submitSharedPublicForm).not.toHaveBeenCalled()
        expect(await screen.findByRole('button', { name: 'Submit Application' })).toBeDisabled()
        fireEvent.click(screen.getByRole('button', { name: 'Back' }))

        const activeFileInput = container.querySelector('input[type="file"]') as HTMLInputElement
        fireEvent.change(activeFileInput, { target: { files: [photo] } })

        fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        fireEvent.click(screen.getByRole('checkbox'))
        fireEvent.click(screen.getByRole('button', { name: 'Submit Application' }))

        await waitFor(() => {
            expect(submitSharedPublicForm).toHaveBeenCalledWith(
                'donor-form',
                { full_name: 'Dana Donor', email: 'dana@example.com' },
                [photo],
                ['profile_photo'],
                undefined,
                undefined,
                'version-1',
                expect.any(String),
                expect.objectContaining({ landing_url: expect.any(String) }),
            )
        })
    })

    it('limits the donor profile photo picker to its field upload types', async () => {
        getSharedPublicForm.mockResolvedValue({
            ...baseForm,
            allowed_mime_types: ['application/pdf', 'image/png', 'image/jpeg'],
            field_allowed_mime_types: { profile_photo: ['image/jpeg', 'image/png'] },
            form_schema: {
                ...baseForm.form_schema,
                pages: [
                    {
                        title: 'Donor Application',
                        fields: [
                            { key: 'profile_photo', label: 'Profile Photo', type: 'file', required: true },
                            { key: 'medical_records', label: 'Medical Records', type: 'file', required: false },
                        ],
                    },
                ],
            },
        })

        render(<PublicIntakeFormClient slug="donor-form" />)

        await screen.findByRole('heading', { name: 'Event Intake Form' })
        const photoInput = screen
            .getByRole('group', { name: 'Profile Photo' })
            .querySelector('input[type="file"]')
        const recordsInput = screen
            .getByRole('group', { name: 'Medical Records' })
            .querySelector('input[type="file"]')
        expect(photoInput).toHaveAttribute('accept', 'image/jpeg,image/png')
        expect(recordsInput).toHaveAttribute('accept', 'application/pdf,image/png,image/jpeg')
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

        vi.useFakeTimers()

        await act(async () => {
            fireEvent.change(screen.getByLabelText(/full name/i), {
                target: { value: 'Resume Person' },
            })
            fireEvent.change(screen.getByLabelText(/dob/i), {
                target: { value: '1992-08-09' },
            })
            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'resume@example.com' },
            })
            await vi.advanceTimersByTimeAsync(700)
        })

        expect(
            screen.getByRole('button', { name: /^continue previous application$/i }),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: /start new/i }))

        fireEvent.change(screen.getByLabelText(/full name/i), {
            target: { value: 'Resume Person ' },
        })

        await act(async () => {
            await vi.advanceTimersByTimeAsync(900)
        })
        expect(
            screen.queryByRole('button', { name: /^continue previous application$/i }),
        ).not.toBeInTheDocument()
        vi.useRealTimers()
    })
})
