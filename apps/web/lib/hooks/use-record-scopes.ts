import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import * as scopes from "@/lib/api/record-scopes"

export function useRoleScopes(role: string, enabled = true) {
    return useQuery({ queryKey: ["record-scopes", "roles", role], queryFn: () => scopes.getRoleScopes(role), enabled: !!role && enabled })
}
export function useScopeAdditions(userId: string, enabled = true) {
    return useQuery({ queryKey: ["record-scopes", "members", userId], queryFn: () => scopes.getScopeAdditions(userId), enabled: !!userId && enabled })
}
export function useScopeMigrationReview(enabled = true) {
    return useQuery({ queryKey: ["record-scopes", "migration-review"], queryFn: scopes.getScopeMigrationReview, enabled })
}
export function useRecordScopeMutation<T>(mutationFn: (input: T) => Promise<unknown>) {
    const client = useQueryClient()
    return useMutation({ mutationFn, onSuccess: () => client.invalidateQueries() })
}
export function useCheckRecordAccess() {
    return useMutation({ mutationFn: scopes.checkRecordAccess })
}
