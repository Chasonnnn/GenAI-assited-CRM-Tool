/**
 * Generic SSE streaming helper.
 */

import { getCsrfHeaders } from '@/lib/csrf';

export type StreamEvent<T> =
    | { type: 'start'; data: { status: string } }
    | { type: 'delta'; data: { text: string } }
    | { type: 'done'; data: T }
    | { type: 'error'; data: { message: string } };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function streamSSE<T>(
    path: string,
    body: unknown,
    onEvent?: (event: StreamEvent<T>) => void,
    options?: { signal?: AbortSignal }
): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        credentials: 'include',
        headers: {
            ...getCsrfHeaders(),
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
        },
        body: JSON.stringify(body),
        ...(options?.signal ? { signal: options.signal } : {}),
    });

    if (!response.ok) {
        let message = response.statusText;
        try {
            const err = await response.json();
            message = err.detail || err.message || message;
        } catch {
            // ignore JSON parse errors
        }
        throw new Error(message);
    }

    if (!response.body) {
        throw new Error('Streaming response not supported');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse: T | null = null;

    const emitEvent = (rawEvent: string) => {
        if (!rawEvent) return;
        let eventType = 'message';
        let data = '';
        for (const line of rawEvent.split('\n')) {
            if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
                data += line.slice(5).trim();
            }
        }

        if (!data) return;
        const parsed = JSON.parse(data);
        const event = { type: eventType, data: parsed } as StreamEvent<T>;
        onEvent?.(event);
        if (event.type === 'done') {
            finalResponse = event.data;
        }
        if (event.type === 'error') {
            throw new Error(event.data.message || 'AI stream error');
        }
    };

    const processBuffer = (flush = false) => {
        buffer = buffer.replace(/\r\n/g, '\n');
        let separatorIndex = buffer.indexOf('\n\n');
        while (separatorIndex !== -1) {
            const rawEvent = buffer.slice(0, separatorIndex).trim();
            buffer = buffer.slice(separatorIndex + 2);
            emitEvent(rawEvent);
            separatorIndex = buffer.indexOf('\n\n');
        }

        if (flush && buffer.trim()) {
            emitEvent(buffer.trim());
            buffer = '';
        }
    };

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        processBuffer();
    }

    processBuffer(true);

    if (finalResponse) {
        return finalResponse;
    }

    throw new Error('AI stream ended without completion');
}
