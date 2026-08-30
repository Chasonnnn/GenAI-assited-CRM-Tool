import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
    archiveDonor,
    createDonorNote,
    createDonor,
    deleteDonorNote,
    getDonor,
    getDonorHistory,
    listDonorNotes,
    listDonors,
    restoreDonor,
    updateDonor,
    updateDonorStatus,
    type DonorFilters,
} from "@/lib/api/donors"
import type {
    DonorCreate,
    DonorNoteCreate,
    DonorStatusUpdate,
    DonorUpdate,
} from "@/lib/types/donor"

export const donorKeys = {
    all: ["donors"] as const,
    lists: () => [...donorKeys.all, "list"] as const,
    list: (filters: DonorFilters) => [...donorKeys.lists(), filters] as const,
    details: () => [...donorKeys.all, "detail"] as const,
    detail: (id: string) => [...donorKeys.details(), id] as const,
    history: (id: string) => [...donorKeys.all, "history", id] as const,
    notes: (id: string) => [...donorKeys.all, "notes", id] as const,
}

export function useDonor(id: string | null) {
    return useQuery({
        queryKey: donorKeys.detail(id ?? ""),
        queryFn: () => getDonor(id!),
        enabled: Boolean(id),
    })
}

export function useDonors(filters: DonorFilters) {
    return useQuery({
        queryKey: donorKeys.list(filters),
        queryFn: () => listDonors(filters),
    })
}

export function useDonorHistory(id: string | null) {
    return useQuery({
        queryKey: donorKeys.history(id ?? ""),
        queryFn: () => getDonorHistory(id!),
        enabled: Boolean(id),
    })
}

export function useDonorNotes(id: string | null) {
    return useQuery({
        queryKey: donorKeys.notes(id ?? ""),
        queryFn: () => listDonorNotes(id!),
        enabled: Boolean(id),
    })
}

export function useCreateDonor() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: DonorCreate) => createDonor(data),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: donorKeys.lists() })
        },
    })
}

export function useUpdateDonor() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: DonorUpdate }) => updateDonor(id, data),
        onSuccess: (donor) => {
            queryClient.setQueryData(donorKeys.detail(donor.id), donor)
            void queryClient.invalidateQueries({ queryKey: donorKeys.lists() })
        },
    })
}

export function useUpdateDonorStatus() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: DonorStatusUpdate }) =>
            updateDonorStatus(id, data),
        onSuccess: (response, { id }) => {
            if (response.donor) {
                queryClient.setQueryData(donorKeys.detail(response.donor.id), response.donor)
            }
            void queryClient.invalidateQueries({ queryKey: donorKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: donorKeys.history(id) })
        },
    })
}

export function useArchiveDonor() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (id: string) => archiveDonor(id),
        onSuccess: (donor) => {
            queryClient.setQueryData(donorKeys.detail(donor.id), donor)
            void queryClient.invalidateQueries({ queryKey: donorKeys.lists() })
        },
    })
}

export function useRestoreDonor() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (id: string) => restoreDonor(id),
        onSuccess: (donor) => {
            queryClient.setQueryData(donorKeys.detail(donor.id), donor)
            void queryClient.invalidateQueries({ queryKey: donorKeys.lists() })
        },
    })
}

export function useCreateDonorNote() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ donorId, data }: { donorId: string; data: DonorNoteCreate }) =>
            createDonorNote(donorId, data),
        onSuccess: (_, { donorId }) => {
            void queryClient.invalidateQueries({ queryKey: donorKeys.notes(donorId) })
            void queryClient.invalidateQueries({ queryKey: donorKeys.detail(donorId) })
        },
    })
}

export function useDeleteDonorNote() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({ donorId, noteId }: { donorId: string; noteId: string }) =>
            deleteDonorNote(donorId, noteId),
        onSuccess: (_, { donorId }) => {
            void queryClient.invalidateQueries({ queryKey: donorKeys.notes(donorId) })
            void queryClient.invalidateQueries({ queryKey: donorKeys.detail(donorId) })
        },
    })
}
