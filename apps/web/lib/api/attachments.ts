/**
 * Attachments API client
 */

import api from "./index"

export interface Attachment {
    id: string
    filename: string
    content_type: string
    file_size: number
    scan_status: "pending" | "clean" | "infected" | "error"
    quarantined: boolean
    uploaded_by_user_id: string
    created_at: string
}

export interface AttachmentDownload {
    download_url: string
    filename: string
}

export const attachmentsApi = {
    /**
     * List attachments for a case
     */
    list: (caseId: string) =>
        api.get<Attachment[]>(`/attachments/cases/${caseId}/attachments`),

    /**
     * Upload a file attachment
     */
    upload: async (caseId: string, file: File): Promise<Attachment> => {
        const formData = new FormData()
        formData.append("file", file)

        return api.upload<Attachment>(
            `/attachments/cases/${caseId}/attachments`,
            formData
        )
    },

    /**
     * Get signed download URL
     */
    getDownloadUrl: (attachmentId: string) =>
        api.get<AttachmentDownload>(`/attachments/${attachmentId}/download`),

    /**
     * Soft-delete an attachment
     */
    delete: (attachmentId: string) =>
        api.delete(`/attachments/${attachmentId}`),
}
