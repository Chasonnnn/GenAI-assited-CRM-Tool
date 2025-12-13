/**
 * API client for backend communication.
 * Handles credentials (cookies) and error responses.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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

interface RequestOptions extends Omit<RequestInit, 'body'> {
    body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers: customHeaders, ...rest } = options;

    const headers: HeadersInit = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest', // CSRF header
        ...customHeaders,
    };

    const config: RequestInit = {
        credentials: 'include', // Send cookies
        headers,
        ...rest,
    };

    if (body !== undefined) {
        config.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${path}`, config);

    if (!response.ok) {
        // Handle auth errors - don't auto-redirect for now
        // if (response.status === 401) {
        //     // Optionally redirect to login
        //     if (typeof window !== 'undefined') {
        //         window.location.href = '/login';
        //     }
        // }

        let message: string | undefined;
        try {
            const err = await response.json();
            message = err.detail || err.message;
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

    patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
        request<T>(path, { method: 'PATCH', body, ...options }),

    delete: <T>(path: string, options?: RequestOptions) =>
        request<T>(path, { method: 'DELETE', ...options }),
};

export default api;
