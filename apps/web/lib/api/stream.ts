/**
 * Generic SSE streaming helper.
 */

import { getCsrfHeaders } from '@/lib/csrf';

export type StreamEvent<T> =
    | { type: 'start'; data: { status: string } }
    | { type: 'delta'; data: { text: string } }
    | { type: 'done'; data: T }
    | { type: 'error'; data: { message: string } };

type StreamDebugState = {
    status: string;
    path: string;
    chunks: number;
    bytes: number;
    events: number;
    lastEvent: string;
    lastChunkBytes: number;
    bufferSize: number;
    contentType: string;
    contentEncoding: string;
    lastUpdate: number;
};

const DEBUG_OVERLAY_ID = 'ai-stream-debug-overlay';

const shouldDebugStream = () => {
    if (typeof window === 'undefined') return false;
    const params = new URLSearchParams(window.location.search);
    if (params.get('ai_stream_debug') === '1') return true;
    try {
        return window.localStorage.getItem('ai_stream_debug') === '1';
    } catch {
        return false;
    }
};

const ensureDebugOverlay = () => {
    if (typeof document === 'undefined') return null;
    let el = document.getElementById(DEBUG_OVERLAY_ID) as HTMLDivElement | null;
    if (el) return el;
    el = document.createElement('div');
    el.id = DEBUG_OVERLAY_ID;
    el.style.position = 'fixed';
    el.style.right = '12px';
    el.style.bottom = '12px';
    el.style.zIndex = '9999';
    el.style.maxWidth = '380px';
    el.style.padding = '10px 12px';
    el.style.borderRadius = '8px';
    el.style.background = 'rgba(0,0,0,0.8)';
    el.style.color = '#fff';
    el.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
    el.style.fontSize = '11px';
    el.style.lineHeight = '1.35';
    el.style.whiteSpace = 'pre-wrap';
    el.style.pointerEvents = 'none';
    document.body.appendChild(el);
    return el;
};

const createStreamDebug = (path: string) => {
    if (!shouldDebugStream()) return null;
    const el = ensureDebugOverlay();
    if (!el) return null;
    const state: StreamDebugState = {
        status: 'connecting',
        path,
        chunks: 0,
        bytes: 0,
        events: 0,
        lastEvent: '',
        lastChunkBytes: 0,
        bufferSize: 0,
        contentType: '',
        contentEncoding: '',
        lastUpdate: Date.now(),
    };

    const render = () => {
        const time = new Date(state.lastUpdate).toLocaleTimeString();
        el.textContent =
            `AI Stream Debug\n` +
            `${state.path}\n` +
            `status: ${state.status}\n` +
            `content-type: ${state.contentType || 'n/a'}\n` +
            `content-encoding: ${state.contentEncoding || 'n/a'}\n` +
            `chunks: ${state.chunks}  bytes: ${state.bytes}\n` +
            `events: ${state.events}  last: ${state.lastEvent || 'n/a'}\n` +
            `last chunk: ${state.lastChunkBytes} bytes\n` +
            `buffer: ${state.bufferSize}\n` +
            `last update: ${time}`;
    };

    const update = (patch: Partial<StreamDebugState>) => {
        Object.assign(state, patch);
        state.lastUpdate = Date.now();
        render();
    };

    render();
    return {
        setHeaders: (contentType: string, contentEncoding: string) =>
            update({ contentType, contentEncoding, status: 'connected' }),
        onChunk: (bytes: number, bufferSize: number) =>
            update({
                chunks: state.chunks + 1,
                bytes: state.bytes + bytes,
                lastChunkBytes: bytes,
                bufferSize,
                status: 'streaming',
            }),
        onEvent: (eventType: string) =>
            update({ events: state.events + 1, lastEvent: eventType }),
        onDone: () => update({ status: 'done' }),
        onError: () => update({ status: 'error' }),
    };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function streamSSE<T>(
    path: string,
    body: unknown,
    onEvent?: (event: StreamEvent<T>) => void,
    options?: { signal?: AbortSignal }
): Promise<T> {
    const debug = createStreamDebug(path);
    let response: Response;
    try {
        response = await fetch(`${API_BASE}${path}`, {
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
    } catch (error) {
        debug?.onError();
        throw error;
    }

    if (!response.ok) {
        debug?.onError();
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

    debug?.setHeaders(
        response.headers.get('content-type') || '',
        response.headers.get('content-encoding') || ''
    );

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse: T | null = null;

    const emitEvent = (rawEvent: string) => {
        if (!rawEvent) return;
        let eventType = 'message';
        const dataLines: string[] = [];
        for (const line of rawEvent.split('\n')) {
            if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
                dataLines.push(line.slice(5));
            }
        }

        const data = dataLines.join('\n').trim();
        if (!data) return;
        const parsed = JSON.parse(data);
        const event = { type: eventType, data: parsed } as StreamEvent<T>;
        onEvent?.(event);
        debug?.onEvent(eventType);
        if (event.type === 'done') {
            finalResponse = event.data;
        }
        if (event.type === 'error') {
            debug?.onError();
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
        debug?.onChunk(value?.length || 0, buffer.length);
        processBuffer();
    }

    processBuffer(true);

    if (finalResponse) {
        debug?.onDone();
        return finalResponse;
    }

    throw new Error('AI stream ended without completion');
}
