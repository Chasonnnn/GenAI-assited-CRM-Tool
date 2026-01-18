/**
 * React Query hooks for Journey module.
 */

import { useQuery } from '@tanstack/react-query';
import * as journeyApi from '../api/journey';

// Query keys
export const journeyKeys = {
    all: ['journey'] as const,
    surrogates: () => [...journeyKeys.all, 'surrogates'] as const,
    surrogate: (id: string) => [...journeyKeys.surrogates(), id] as const,
};

/**
 * Fetch journey timeline for a surrogate.
 * Returns phases and milestones with computed statuses.
 */
export function useSurrogateJourney(surrogateId: string, enabled: boolean = true) {
    return useQuery({
        queryKey: journeyKeys.surrogate(surrogateId),
        queryFn: () => journeyApi.getSurrogateJourney(surrogateId),
        enabled: !!surrogateId && enabled,
        staleTime: 5 * 60 * 1000, // 5 minutes - journey data doesn't change frequently
    });
}
