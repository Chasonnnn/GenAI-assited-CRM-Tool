import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../lib/api.ts', () => {
    const api = {
        get: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
    }
    return {
        api,
        default: api,
        ApiError: class ApiError extends Error {},
    }
})

import { api } from '../lib/api.ts'
import { acceptConsent, approveAction, rejectAction, sendChatMessage, testAPIKey } from '../lib/api/ai'

type ApiMock = {
    get: ReturnType<typeof vi.fn>
    post: ReturnType<typeof vi.fn>
    patch: ReturnType<typeof vi.fn>
    delete: ReturnType<typeof vi.fn>
}

const apiMock = api as unknown as ApiMock

describe('AI API client contract', () => {
    beforeEach(() => {
        apiMock.get.mockReset()
        apiMock.post.mockReset()
        apiMock.patch.mockReset()
        apiMock.delete.mockReset()
    })

    it('uses /ai/settings/test for API key test', async () => {
        apiMock.post.mockResolvedValue({ valid: true })
        await testAPIKey('gemini', 'k')
        expect(api.post).toHaveBeenCalledWith('/ai/settings/test', { provider: 'gemini', api_key: 'k' })
    })

    it('uses /ai/consent/accept for consent acceptance', async () => {
        apiMock.post.mockResolvedValue({ accepted: true })
        await acceptConsent()
        expect(api.post).toHaveBeenCalledWith('/ai/consent/accept')
    })

    it('uses /ai/chat/async for chat messages', async () => {
        apiMock.post.mockResolvedValue({ job_id: 'j1', status: 'pending' })
        apiMock.get.mockResolvedValue({
            job_id: 'j1',
            status: 'completed',
            result: { content: 'ok', proposed_actions: [], tokens_used: { prompt: 0, completion: 0, total: 0 } },
        })
        await sendChatMessage({ entity_type: 'surrogate', entity_id: 's1', message: 'hello' })
        expect(api.post).toHaveBeenCalledWith('/ai/chat/async', { entity_type: 'surrogate', entity_id: 's1', message: 'hello' })
        expect(api.get).toHaveBeenCalledWith('/ai/chat/jobs/j1')
    })

    it('uses /ai/actions/{id}/approve|reject for action decisions', async () => {
        apiMock.post.mockResolvedValue({ success: true })
        await approveAction('a1')
        await rejectAction('a2')
        expect(api.post).toHaveBeenCalledWith('/ai/actions/a1/approve')
        expect(api.post).toHaveBeenCalledWith('/ai/actions/a2/reject')
    })
})
