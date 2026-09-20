import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Page from '@/app/ops/cli/page.client'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), delete: vi.fn(), error: vi.fn() }))
vi.mock('@/lib/api', () => ({ default: mocks }))
vi.mock('@/components/ui/toast', () => ({ toast: { error: mocks.error } }))

const session = { id: 'session-id', created_at: '2026-09-19T00:00:00Z', expires_at: '2099-09-19T08:00:00Z', revoked_at: null }

function mount() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    return render(<QueryClientProvider client={client}><Page /></QueryClientProvider>)
}

describe('OPS CLI login', () => {
    beforeEach(() => {
        vi.resetAllMocks()
        mocks.get.mockResolvedValue([])
        mocks.post.mockResolvedValue({ approved: true })
        mocks.delete.mockResolvedValue(undefined)
    })

    it('approves only on submit and never creates or displays a credential', async () => {
        mount()
        expect(await screen.findByText('No CLI sessions.')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Sign in to CLI' })).toBeDisabled()
        fireEvent.change(screen.getByLabelText('Code from your terminal'), { target: { value: 'ABCD-EFGH-JKLM' } })
        expect(mocks.post).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole('button', { name: 'Sign in to CLI' }))
        expect(await screen.findByRole('status')).toHaveTextContent('Approved. Return to your terminal.')
        expect(mocks.post).toHaveBeenCalledExactlyOnceWith('/platform/cli/login/approve', { code: 'ABCD-EFGH-JKLM' })
        expect(screen.queryByText('Create credential')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Connect another terminal' }))
        expect(await screen.findByLabelText('Code from your terminal')).toHaveValue('')
    })

    it('keeps the entered code after an approval error and allows retry', async () => {
        mocks.post.mockRejectedValueOnce(new Error('expired'))
        mount()
        fireEvent.change(screen.getByLabelText('Code from your terminal'), { target: { value: 'ABCD-EFGH-JKLM' } })
        fireEvent.click(screen.getByRole('button', { name: 'Sign in to CLI' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Unable to approve.')
        expect(screen.getByLabelText('Code from your terminal')).toHaveValue('ABCD-EFGH-JKLM')
        fireEvent.click(screen.getByRole('button', { name: 'Sign in to CLI' }))
        expect(await screen.findByRole('status')).toHaveTextContent('Approved.')
    })

    it('signs out an existing session', async () => {
        mocks.get.mockResolvedValue([session])
        mount()
        const button = await screen.findByRole('button', { name: 'Sign out' })
        mocks.get.mockResolvedValue([{ ...session, revoked_at: '2026-09-19T01:00:00Z' }])
        fireEvent.click(button)
        expect(await screen.findByText('Signed out')).toBeInTheDocument()
        expect(mocks.delete).toHaveBeenCalledWith('/platform/cli/tokens/session-id')
    })

    it('retries loading after a failure', async () => {
        mocks.get.mockRejectedValue(new Error('network'))
        mount()
        expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load CLI sessions.')
        mocks.get.mockResolvedValue([])
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
        await waitFor(() => expect(screen.getByText('No CLI sessions.')).toBeInTheDocument())
    })
})
