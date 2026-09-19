"use client"

import { EntityDocuments } from "@/components/documents/EntityDocuments"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useDeleteDonorAttachment, useDonorAttachments, useDownloadAttachment, useUploadDonorAttachment } from "@/lib/hooks/use-attachments"
import type { Donor } from "@/lib/types/donor"

export function DonorDocumentsSection({ donor, canEdit, embedded = false }: { donor: Donor; canEdit: boolean; embedded?: boolean }) {
    const query = useDonorAttachments(donor.id)
    const upload = useUploadDonorAttachment()
    const download = useDownloadAttachment()
    const remove = useDeleteDonorAttachment()
    const content = <EntityDocuments
                attachments={query.data ?? []}
                isLoading={query.isLoading}
                isError={query.isError}
                onRetry={query.refetch}
                onUpload={(file) => upload.mutateAsync({ donorId: donor.id, file })}
                onDownload={(id) => download.mutate(id)}
                onDelete={(attachmentId) => remove.mutateAsync({ donorId: donor.id, attachmentId })}
                isUploading={upload.isPending}
                isDownloading={download.isPending}
                isDeleting={remove.isPending}
                canEdit={canEdit}
                inputLabel="Upload donor documents"
                listLabel="Donor documents"
                loadingLabel="Loading documents…"
                emptyLabel="No documents yet"
            />
    if (embedded) return <><div className="mb-4 flex items-center justify-between"><h3 className="text-lg font-semibold">Attachments</h3></div>{content}</>
    return <Card><CardHeader><CardTitle><h2>Documents</h2></CardTitle></CardHeader><CardContent>{content}</CardContent></Card>
}
