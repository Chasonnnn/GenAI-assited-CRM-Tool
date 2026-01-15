/**
 * Search API client - global search functionality.
 */

import api from './index';

export interface SearchResult {
    entity_type: "surrogate" | "note" | "attachment" | "intended_parent"
    entity_id: string
    title: string
    snippet: string
    rank: number
    surrogate_id: string | null
    surrogate_name: string | null
}

export interface SearchResponse {
    query: string
    total: number
    results: SearchResult[]
}

export interface SearchParams {
    q: string
    types?: string
    limit?: number
    offset?: number
}

/**
 * Global search across surrogates, notes, attachments, and intended parents.
 */
export function globalSearch(params: SearchParams): Promise<SearchResponse> {
    const searchParams = new URLSearchParams();
    searchParams.set('q', params.q);
    if (params.types) searchParams.set('types', params.types);
    if (params.limit) searchParams.set('limit', String(params.limit));
    if (params.offset) searchParams.set('offset', String(params.offset));

    return api.get<SearchResponse>(`/search?${searchParams.toString()}`);
}
