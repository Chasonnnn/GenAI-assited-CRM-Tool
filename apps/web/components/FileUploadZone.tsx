"use client"

import { EntityDocuments } from "@/components/documents/EntityDocuments"
import { useUploadAttachment, useAttachments, useDownloadAttachment, useDeleteAttachment } from "@/lib/hooks/use-attachments"

export function FileUploadZone({ surrogateId, className }: { surrogateId: string; className?: string }) {
    const query = useAttachments(surrogateId)
    const upload = useUploadAttachment()
    const download = useDownloadAttachment()
    const remove = useDeleteAttachment()
    return <EntityDocuments
        attachments={query.data ?? []}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={query.refetch}
        onUpload={(file) => upload.mutateAsync({ surrogateId, file })}
        onDownload={(id) => download.mutate(id)}
        onDelete={(attachmentId) => remove.mutateAsync({ surrogateId, attachmentId })}
        isUploading={upload.isPending}
        isDownloading={download.isPending}
        isDeleting={remove.isPending}
        emptyDescription="Upload documents to keep surrogate records complete."
        {...(className ? { className } : {})}
    />
}
