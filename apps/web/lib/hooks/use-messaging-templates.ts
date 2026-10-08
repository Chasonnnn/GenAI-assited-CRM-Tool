/** React Query hooks for text message templates, test phones, and test texts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import * as twilioApi from "@/lib/api/twilio"
import type { MessagingTemplateCreate, MessagingTemplateDraftUpdate } from "@/lib/api/twilio"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"

export const messagingTemplateKeys = {
    all: ["messaging-templates"] as const,
    versions: () => [...messagingTemplateKeys.all, "versions"] as const,
    usage: () => [...messagingTemplateKeys.all, "usage"] as const,
    variables: () => [...messagingTemplateKeys.all, "variables"] as const,
    testPhones: () => ["messaging-test-phones"] as const,
}

/** Every version of every template; the library groups them by template_key. */
export function useMessagingTemplateVersions(enabled = true) {
    return useQuery({
        queryKey: messagingTemplateKeys.versions(),
        queryFn: () => twilioApi.listMessagingTemplates(),
        enabled,
    })
}

export function useMessagingTemplateUsage(enabled = true) {
    return useQuery({
        queryKey: messagingTemplateKeys.usage(),
        queryFn: twilioApi.listMessagingTemplateUsage,
        enabled,
    })
}

export function useMessagingSmsVariables(enabled = true) {
    return useQuery({
        queryKey: messagingTemplateKeys.variables(),
        queryFn: twilioApi.listMessagingSmsVariables,
        enabled,
        staleTime: 5 * 60 * 1000,
    })
}

export function useMessagingTestPhones(enabled = true) {
    return useQuery({
        queryKey: messagingTemplateKeys.testPhones(),
        queryFn: twilioApi.listMessagingTestPhones,
        enabled,
    })
}

function useInvalidateTemplates() {
    const queryClient = useQueryClient()
    // Prefix match also refreshes the campaign wizard's published-template list.
    return () => queryClient.invalidateQueries({ queryKey: messagingTemplateKeys.all })
}

export function useCreateMessagingTemplate() {
    const invalidate = useInvalidateTemplates()
    return useMutation({
        mutationFn: (template: MessagingTemplateCreate) => twilioApi.createMessagingTemplate(template),
        onSuccess: () => void invalidate(),
    })
}

export function useSaveMessagingTemplateDraft() {
    const invalidate = useInvalidateTemplates()
    return useMutation({
        /** Edits the draft in place, or starts the next draft when the latest version is published. */
        mutationFn: ({
            templateKey,
            draftId,
            update,
        }: {
            templateKey: string
            draftId: string | null
            update: MessagingTemplateDraftUpdate
        }) =>
            draftId
                ? twilioApi.updateMessagingTemplateDraft(draftId, update)
                : twilioApi.createMessagingTemplateVersion(templateKey, update),
        onSuccess: () => void invalidate(),
    })
}

export function usePublishMessagingTemplate() {
    const invalidate = useInvalidateTemplates()
    return useMutation({
        mutationFn: (templateId: string) => twilioApi.publishMessagingTemplate(templateId),
        onSuccess: () => void invalidate(),
    })
}

export function useSendMessagingTemplateTest() {
    return useMutation({
        mutationFn: ({ templateId, testPhoneId }: { templateId: string; testPhoneId: string }) =>
            twilioApi.sendMessagingTemplateTest(templateId, testPhoneId),
    })
}

function useTestPhoneMutation<TArgs, TResult>(mutationFn: (args: TArgs) => Promise<TResult>) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn,
        onSettled: () =>
            void queryClient.invalidateQueries({ queryKey: messagingTemplateKeys.testPhones() }),
    })
}

export function useAddMessagingTestPhone() {
    return useTestPhoneMutation(twilioApi.addMessagingTestPhone)
}

export function useVerifyMessagingTestPhone() {
    return useTestPhoneMutation(({ id, code }: { id: string; code: string }) =>
        twilioApi.verifyMessagingTestPhone(id, code),
    )
}

export function useRemoveMessagingTestPhone() {
    return useTestPhoneMutation(twilioApi.removeMessagingTestPhone)
}

/** The messaging APIs require an admin or developer with manage_integrations. */
export function useMessagingAccess(): { loading: boolean; allowed: boolean } {
    const { user, isLoading } = useAuth()
    const isDeveloper = user?.role === "developer"
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    if (isLoading || !user) return { loading: isLoading, allowed: false }
    if (isDeveloper) return { loading: false, allowed: true }
    if (user.role !== "admin") return { loading: false, allowed: false }
    if (permissionsQuery.isLoading) return { loading: true, allowed: false }
    return {
        loading: false,
        allowed: (permissionsQuery.data?.permissions ?? []).includes("manage_integrations"),
    }
}
