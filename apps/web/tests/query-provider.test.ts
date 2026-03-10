import { describe, expect, it } from 'vitest'

import { ApiError } from '../lib/api'
import { shouldRetryQuery } from '../lib/query-provider'

describe('shouldRetryQuery', () => {
    it('does not retry auth or rate limit errors', () => {
        expect(shouldRetryQuery(0, new ApiError(401, 'Unauthorized'))).toBe(false)
        expect(shouldRetryQuery(0, new ApiError(403, 'Forbidden'))).toBe(false)
        expect(shouldRetryQuery(0, new ApiError(429, 'Too Many Requests'))).toBe(false)
    })

    it('retries other failures up to the second failure', () => {
        expect(shouldRetryQuery(0, new Error('boom'))).toBe(true)
        expect(shouldRetryQuery(1, new ApiError(500, 'Internal Server Error'))).toBe(true)
        expect(shouldRetryQuery(2, new ApiError(500, 'Internal Server Error'))).toBe(false)
    })
})
