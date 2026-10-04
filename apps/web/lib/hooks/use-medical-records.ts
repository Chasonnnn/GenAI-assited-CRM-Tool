import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"

import { ApiError } from "@/lib/api"
import {
    archiveMedicalRecord,
    correctMedicalRecord,
    createMedicalRecord,
    listMedicalRecords,
    restoreMedicalRecordSection,
} from "@/lib/api/medical-records"
import { entityActivityKeys } from "@/lib/hooks/use-entity-activity"
import { surrogateKeys } from "@/lib/hooks/use-surrogates"
import type {
    MedicalRecordCreate,
    MedicalRecordListResponse,
    MedicalRecordOwner,
    MedicalRecordSection,
    MedicalRecordUpdate,
} from "@/lib/types/medical-record"

export const medicalRecordKeys = {
    all: ["medical-records"] as const,
    owner: (owner: MedicalRecordOwner) => [...medicalRecordKeys.all, owner.kind, owner.id] as const,
}

export function useMedicalRecords(owner: MedicalRecordOwner) {
    return useQuery({
        queryKey: medicalRecordKeys.owner(owner),
        queryFn: () => listMedicalRecords(owner),
    })
}

function afterWrite(queryClient: QueryClient, owner: MedicalRecordOwner, data: MedicalRecordListResponse) {
    queryClient.setQueryData(medicalRecordKeys.owner(owner), data)
    if (owner.kind === "surrogate") {
        void queryClient.invalidateQueries({ queryKey: surrogateKeys.activity(owner.id) })
        void queryClient.invalidateQueries({ queryKey: ["analytics", "activity-feed"], exact: false })
    } else {
        void queryClient.invalidateQueries({ queryKey: entityActivityKeys.entity("donor", owner.id) })
    }
}

function refetchOnConflict(queryClient: QueryClient, owner: MedicalRecordOwner, error: unknown) {
    if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: medicalRecordKeys.owner(owner) })
    }
}

export function useCreateMedicalRecord(owner: MedicalRecordOwner) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: MedicalRecordCreate) => createMedicalRecord(owner, data),
        onSuccess: (data) => afterWrite(queryClient, owner, data),
        onError: (error) => refetchOnConflict(queryClient, owner, error),
    })
}

export function useCorrectMedicalRecord(owner: MedicalRecordOwner) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ recordId, data }: { recordId: string; data: MedicalRecordUpdate }) =>
            correctMedicalRecord(owner, recordId, data),
        onSuccess: (data) => afterWrite(queryClient, owner, data),
        onError: (error) => refetchOnConflict(queryClient, owner, error),
    })
}

export function useArchiveMedicalRecord(owner: MedicalRecordOwner) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ recordId, expectedRevision }: { recordId: string; expectedRevision: number }) =>
            archiveMedicalRecord(owner, recordId, expectedRevision),
        onSuccess: (data) => afterWrite(queryClient, owner, data),
        onError: (error) => refetchOnConflict(queryClient, owner, error),
    })
}

export function useRestoreMedicalRecordSection(owner: MedicalRecordOwner) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ section, idempotencyKey }: { section: MedicalRecordSection; idempotencyKey: string }) =>
            restoreMedicalRecordSection(owner, section, idempotencyKey),
        onSuccess: (data) => afterWrite(queryClient, owner, data),
        onError: (error) => refetchOnConflict(queryClient, owner, error),
    })
}
