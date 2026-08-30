"use client"

import { useRef } from "react"
import { CameraIcon, Loader2Icon, UserRoundIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { toast } from "@/components/ui/toast"
import {
    useAttachmentPreviewUrl,
    useUploadDonorProfilePhoto,
} from "@/lib/hooks/use-attachments"
import type { Donor } from "@/lib/types/donor"

const PROFILE_PHOTO_TYPES = new Set(["image/jpeg", "image/png"])

export function DonorProfilePhoto({
    donor,
    canEdit,
    compact = false,
}: {
    donor: Donor
    canEdit: boolean
    compact?: boolean
}) {
    const inputRef = useRef<HTMLInputElement>(null)
    const previewQuery = useAttachmentPreviewUrl(donor.profile_photo_attachment_id)
    const uploadPhoto = useUploadDonorProfilePhoto()
    const hasPhotoPointer = Boolean(donor.profile_photo_attachment_id)
    const hasPhoto = Boolean(donor.profile_photo_attachment_id && previewQuery.data?.download_url)
    const inputLabel = hasPhotoPointer ? "Replace donor profile photo" : "Upload donor profile photo"
    const fileInputLabel = hasPhotoPointer
        ? "Choose replacement donor profile photo"
        : "Choose donor profile photo"

    const handlePhoto = async (file: File | undefined) => {
        if (!file) return
        if (!PROFILE_PHOTO_TYPES.has(file.type)) {
            toast.error("Profile photo must be a JPG or PNG image")
            return
        }
        try {
            await uploadPhoto.mutateAsync({ donorId: donor.id, file })
            toast.success("Profile photo updated")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to upload profile photo")
        }
    }

    return (
        <div className={compact ? "relative size-10 shrink-0" : "relative size-14 shrink-0"}>
            <Avatar className={compact ? "size-10" : "size-14"}>
                {hasPhoto ? (
                    <AvatarImage
                        src={previewQuery.data?.download_url}
                        alt={`${donor.full_name} profile photo`}
                    />
                ) : null}
                <AvatarFallback>
                    <UserRoundIcon className={compact ? "size-5" : "size-7"} aria-hidden="true" />
                </AvatarFallback>
            </Avatar>
            {canEdit ? (
                <>
                    <input
                        ref={inputRef}
                        type="file"
                        accept="image/jpeg,image/png"
                        className="sr-only"
                        aria-label={fileInputLabel}
                        onChange={(event) => {
                            void handlePhoto(event.target.files?.[0])
                            event.target.value = ""
                        }}
                    />
                    <Button
                        type="button"
                        size="icon-sm"
                        variant="secondary"
                        className={compact
                            ? "absolute -bottom-1 -right-1 size-6 rounded-full border bg-background"
                            : "absolute -bottom-1 -right-1 rounded-full border bg-background"}
                        aria-label={inputLabel}
                        disabled={uploadPhoto.isPending}
                        onClick={() => inputRef.current?.click()}
                    >
                        {uploadPhoto.isPending ? (
                            <Loader2Icon className="size-3 animate-spin" />
                        ) : (
                            <CameraIcon className="size-3" />
                        )}
                    </Button>
                </>
            ) : null}
        </div>
    )
}
