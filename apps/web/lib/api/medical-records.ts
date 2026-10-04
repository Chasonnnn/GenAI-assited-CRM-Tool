import api from "@/lib/api"
import type {
    MedicalRecordCreate,
    MedicalRecordListResponse,
    MedicalRecordOwner,
    MedicalRecordSection,
    MedicalRecordUpdate,
} from "@/lib/types/medical-record"

function basePath(owner: MedicalRecordOwner): string {
    const collection = owner.kind === "surrogate" ? "surrogates" : "donors"
    return `/${collection}/${owner.id}/medical-records`
}

export function listMedicalRecords(owner: MedicalRecordOwner): Promise<MedicalRecordListResponse> {
    return api.get<MedicalRecordListResponse>(basePath(owner))
}

export function createMedicalRecord(
    owner: MedicalRecordOwner,
    data: MedicalRecordCreate,
): Promise<MedicalRecordListResponse> {
    return api.post<MedicalRecordListResponse>(basePath(owner), data)
}

export function correctMedicalRecord(
    owner: MedicalRecordOwner,
    recordId: string,
    data: MedicalRecordUpdate,
): Promise<MedicalRecordListResponse> {
    return api.patch<MedicalRecordListResponse>(`${basePath(owner)}/${recordId}`, data)
}

export function archiveMedicalRecord(
    owner: MedicalRecordOwner,
    recordId: string,
    expectedRevision: number,
): Promise<MedicalRecordListResponse> {
    return api.post<MedicalRecordListResponse>(`${basePath(owner)}/${recordId}/archive`, {
        expected_revision: expectedRevision,
    })
}

export function restoreMedicalRecordSection(
    owner: MedicalRecordOwner,
    section: MedicalRecordSection,
    idempotencyKey: string,
): Promise<MedicalRecordListResponse> {
    return api.post<MedicalRecordListResponse>(`${basePath(owner)}/sections/${section}/restore`, {
        idempotency_key: idempotencyKey,
    })
}
