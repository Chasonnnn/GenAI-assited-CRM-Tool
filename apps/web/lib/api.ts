/**
 * API client for backend communication.
 * Handles credentials (cookies), error responses, and rate limiting.
 */

import { getCsrfHeaders } from '@/lib/csrf';
import { getApiBase } from '@/lib/api-base';
import { toast } from 'sonner';

const API_BASE = getApiBase();
const MAX_RETRIES = 2;
const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 8000;

export class ApiError extends Error {
    constructor(
        public status: number,
        public statusText: string,
        message?: string
    ) {
        super(message || `${status} ${statusText}`);
        this.name = 'ApiError';
    }
}

export class RateLimitError extends ApiError {
    constructor(public retryAfter: number | null) {
        super(429, 'Too Many Requests', 'Rate limit exceeded');
        this.name = 'RateLimitError';
    }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
    body?: unknown;
    /** Internal: current retry count */
    _retryCount?: number;
}

/**
 * Check if a path is an expensive endpoint (search, reports, exports).
 * These should not auto-retry on rate limit.
 */
function isExpensiveEndpoint(path: string): boolean {
    return /\/(search|reports|export|analytics)/.test(path);
}

function parseRetryAfter(header: string | null): number | null {
    if (!header) return null;

    const asInt = Number(header);
    if (Number.isFinite(asInt)) {
        return Math.max(0, Math.floor(asInt));
    }

    const dateMs = Date.parse(header);
    if (!Number.isNaN(dateMs)) {
        const diffSeconds = Math.ceil((dateMs - Date.now()) / 1000);
        return Math.max(0, diffSeconds);
    }

    return null;
}

function getRetryDelayMs(retryAfterSeconds: number | null, retryCount: number): number {
    if (retryAfterSeconds !== null) {
        return retryAfterSeconds * 1000;
    }
    const backoff = BASE_BACKOFF_MS * Math.pow(2, retryCount);
    return Math.min(backoff, MAX_BACKOFF_MS);
}

/**
 * Sleep for a given number of milliseconds.
 */
function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers: customHeaders, _retryCount = 0, ...rest } = options;
    const method = (options.method || 'GET').toUpperCase();

    // Check if body is FormData - don't set Content-Type (browser sets multipart boundary)
    const isFormData = body instanceof FormData;

    const headers: HeadersInit = {
        ...getCsrfHeaders(),
        ...(!isFormData && { 'Content-Type': 'application/json' }),
        ...customHeaders,
    };

    const config: RequestInit = {
        credentials: 'include', // Send cookies
        headers,
        ...rest,
    };

    if (body !== undefined) {
        // Don't JSON.stringify FormData - pass it directly
        config.body = isFormData ? (body as FormData) : JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${path}`, config);

    // Handle rate limiting (429)
    if (response.status === 429) {
        const retryAfterSeconds = parseRetryAfter(response.headers.get('Retry-After'));

        // Only auto-retry for non-expensive GET requests
        const isGetRequest = method === 'GET';
        const canAutoRetry = isGetRequest && !isExpensiveEndpoint(path) && _retryCount < MAX_RETRIES;

        if (canAutoRetry) {
            // Auto-retry with Retry-After when provided, otherwise exponential backoff
            const delayMs = getRetryDelayMs(retryAfterSeconds, _retryCount);
            await sleep(delayMs);
            return request<T>(path, { ...options, _retryCount: _retryCount + 1 });
        }

        // Show toast for user feedback
        const waitMessage = retryAfterSeconds
            ? `Please wait ${retryAfterSeconds} seconds.`
            : 'Please try again later.';
        toast.error(`Too many requests. ${waitMessage}`);

        throw new RateLimitError(retryAfterSeconds);
    }

    if (!response.ok) {
        let message: string | undefined;
        try {
            const err = await response.json();
            // Handle FastAPI validation errors (array of {loc, msg, type})
            if (Array.isArray(err.detail)) {
                message = err.detail
                    .map((e: { loc?: string[]; msg?: string }) =>
                        e.loc ? `${e.loc.slice(1).join('.')}: ${e.msg}` : e.msg
                    )
                    .join('; ');
            } else {
                message = err.detail || err.message;
            }
        } catch {
            // Ignore JSON parse errors
        }

        throw new ApiError(response.status, response.statusText, message);
    }

    // Handle 204 No Content
    if (response.status === 204) {
        return undefined as T;
    }

    return response.json();
}

// Convenience methods
export const api = {
    get: <T>(path: string, options?: RequestOptions) =>
        request<T>(path, { method: 'GET', ...options }),

    post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
        request<T>(path, { method: 'POST', body, ...options }),

    put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
        request<T>(path, { method: 'PUT', body, ...options }),

    patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
        request<T>(path, { method: 'PATCH', body, ...options }),

    delete: <T>(path: string, options?: RequestOptions) =>
        request<T>(path, { method: 'DELETE', ...options }),

    /**
     * Upload files via FormData.
     * Automatically handles multipart encoding.
     */
    upload: <T>(path: string, formData: FormData, options?: Omit<RequestOptions, 'body'>) =>
        request<T>(path, { method: 'POST', body: formData, ...options }),
};

export default api;
