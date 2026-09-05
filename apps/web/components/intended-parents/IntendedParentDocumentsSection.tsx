"use client"

import { EntityDocuments } from "@/components/documents/EntityDocuments"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useDeleteIPAttachment, useIPAttachments, useDownloadAttachment, useUploadIPAttachment } from "@/lib/hooks/use-attachments"

export function IntendedParentDocumentsSection({ intendedParentId, canEdit }: { intendedParentId: string; canEdit: boolean }) {
    const query = useIPAttachments(intendedParentId)
    const upload = useUploadIPAttachment()
    const download = useDownloadAttachment()
    const remove = useDeleteIPAttachment()
    return <Card>
        <CardHeader><CardTitle><h2>Documents</h2></CardTitle></CardHeader>
        <CardContent>
            <EntityDocuments
                attachments={query.data ?? []}
                isLoading={query.isLoading}
                isError={query.isError}
                onRetry={query.refetch}
                onUpload={(file) => upload.mutateAsync({ ipId: intendedParentId, file })}
                onDownload={(id) => download.mutate(id)}
                onDelete={(attachmentId) => remove.mutateAsync({ ipId: intendedParentId, attachmentId })}
                isUploading={upload.isPending}
                isDownloading={download.isPending}
                isDeleting={remove.isPending}
                canEdit={canEdit}
                inputLabel="Upload intended parent documents"
                listLabel="Intended parent documents"
                loadingLabel="Loading documents…"
                emptyLabel="No documents yet"
            />
        </CardContent>
    </Card>
}
