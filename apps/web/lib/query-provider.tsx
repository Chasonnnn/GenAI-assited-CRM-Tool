'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
    if (error instanceof Error && 'status' in error) {
        const status = (error as { status: number }).status;
        if (status === 401 || status === 403 || status === 429) {
            return false;
        }
    }
    return failureCount < 2;
}

export function QueryProvider({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 60 * 1000, // 1 minute
                        retry: shouldRetryQuery,
                    },
                },
            })
    );

    return (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
}
