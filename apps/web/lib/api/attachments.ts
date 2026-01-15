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
    uploaded_by_user_id: string | null
    created_at: string
}

export interface AttachmentDownload {
    download_url: string
    filename: string
}

export const attachmentsApi = {
    /**
     * List attachments for a surrogate
     */
    list: (surrogateId: string) =>
        api.get<Attachment[]>(`/attachments/surrogates/${surrogateId}/attachments`),

    /**
     * Upload a file attachment
     */
    upload: async (surrogateId: string, file: File): Promise<Attachment> => {
        const formData = new FormData()
        formData.append("file", file)

        return api.upload<Attachment>(
            `/attachments/surrogates/${surrogateId}/attachments`,
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

    /**
     * List attachments for an Intended Parent
     */
    listForIP: (ipId: string) =>
        api.get<Attachment[]>(`/attachments/intended-parents/${ipId}/attachments`),

    /**
     * Upload a file attachment for an Intended Parent
     */
    uploadForIP: async (ipId: string, file: File): Promise<Attachment> => {
        const formData = new FormData()
        formData.append("file", file)

        return api.upload<Attachment>(
            `/attachments/intended-parents/${ipId}/attachments`,
            formData
        )
    },
}
