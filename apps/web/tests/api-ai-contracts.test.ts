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

describe('AI API client contract', () => {
    beforeEach(() => {
        ;(api.get as any).mockReset()
        ;(api.post as any).mockReset()
        ;(api.patch as any).mockReset()
        ;(api.delete as any).mockReset()
    })

    it('uses /ai/settings/test for API key test', async () => {
        ;(api.post as any).mockResolvedValue({ valid: true })
        await testAPIKey('openai', 'k')
        expect(api.post).toHaveBeenCalledWith('/ai/settings/test', { provider: 'openai', api_key: 'k' })
    })

    it('uses /ai/consent/accept for consent acceptance', async () => {
        ;(api.post as any).mockResolvedValue({ accepted: true })
        await acceptConsent()
        expect(api.post).toHaveBeenCalledWith('/ai/consent/accept')
    })

    it('uses /ai/chat for chat messages', async () => {
        ;(api.post as any).mockResolvedValue({ content: 'ok', proposed_actions: [], tokens_used: { prompt: 0, completion: 0, total: 0 } })
        await sendChatMessage({ entity_type: 'case', entity_id: 'c1', message: 'hello' })
        expect(api.post).toHaveBeenCalledWith('/ai/chat', { entity_type: 'case', entity_id: 'c1', message: 'hello' })
    })

    it('uses /ai/actions/{id}/approve|reject for action decisions', async () => {
        ;(api.post as any).mockResolvedValue({ success: true })
        await approveAction('a1')
        await rejectAction('a2')
        expect(api.post).toHaveBeenCalledWith('/ai/actions/a1/approve')
        expect(api.post).toHaveBeenCalledWith('/ai/actions/a2/reject')
    })
})

