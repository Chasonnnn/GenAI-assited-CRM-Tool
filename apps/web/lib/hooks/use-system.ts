/**
 * React Query hooks for system metadata.
 */

import { useQuery } from '@tanstack/react-query';
import * as systemApi from '../api/system';

export const systemKeys = {
    all: ['system'] as const,
    health: () => [...systemKeys.all, 'health'] as const,
};

export function useSystemHealth() {
    return useQuery({
        queryKey: systemKeys.health(),
        queryFn: systemApi.getSystemHealth,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
}
