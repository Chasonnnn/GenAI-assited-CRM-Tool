"use client"

import { useRef, useState } from "react"
import { Loader2Icon, TrashIcon, UploadIcon } from "lucide-react"

import { OrgLogoTile } from "@/components/org-logo-tile"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { toast } from "@/components/ui/toast"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { useDeleteOrganizationLogo, useUploadOrganizationLogo } from "@/lib/hooks/use-settings"

const ACCEPTED_LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"]
// Matches the API upload limit (MAX_LOGO_UPLOAD_BYTES); the API compresses the stored logo.
const MAX_LOGO_UPLOAD_BYTES = 1024 * 1024

/** Square logo shown in the app sidebar, separate from the email signature logo. */
export function SidebarLogoField({ orgName, logoUrl }: { orgName: string; logoUrl: string | null }) {
    const inputRef = useRef<HTMLInputElement>(null)
    const uploadLogo = useUploadOrganizationLogo()
    const deleteLogo = useDeleteOrganizationLogo()
    const [error, setError] = useState<string | null>(null)
    const busy = uploadLogo.isPending || deleteLogo.isPending

    const handleFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        // Reset so choosing the same file again still fires change.
        event.target.value = ""
        if (!file) return
        if (!ACCEPTED_LOGO_TYPES.includes(file.type)) {
            setError("Logo must be a PNG, JPG or WebP image.")
            return
        }
        if (file.size > MAX_LOGO_UPLOAD_BYTES) {
            setError("Logo must be 1 MB or smaller.")
            return
        }
        setError(null)
        try {
            await uploadLogo.mutateAsync(file)
            toast.success("Sidebar logo updated")
        } catch (uploadError) {
            setError(getActionErrorMessage(uploadError, "Couldn't upload the logo. Try again."))
        }
    }

    const handleRemove = async () => {
        setError(null)
        await deleteLogo.mutateAsync()
        toast.success("Sidebar logo removed")
    }

    return (
        <div className="space-y-3">
            <h4 id="sidebar-logo-label" className="text-sm font-medium">
                Sidebar logo
            </h4>
            <div className="flex items-center gap-4" role="group" aria-labelledby="sidebar-logo-label">
                <OrgLogoTile name={orgName} logoUrl={logoUrl} size="lg" />
                <div className="flex flex-wrap items-center gap-2">
                    <input
                        ref={inputRef}
                        id="sidebar-logo-upload"
                        name="sidebar_logo_upload"
                        type="file"
                        accept={ACCEPTED_LOGO_TYPES.join(",")}
                        aria-label="Sidebar logo file"
                        className="hidden"
                        onChange={(event) => void handleFile(event)}
                    />
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => inputRef.current?.click()}
                    >
                        {uploadLogo.isPending ? (
                            <Loader2Icon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        ) : (
                            <UploadIcon aria-hidden="true" />
                        )}
                        {uploadLogo.isPending ? "Uploading…" : logoUrl ? "Replace logo" : "Upload logo"}
                    </Button>
                    {logoUrl ? (
                        <ConfirmDialog
                            trigger={
                                <Button type="button" variant="destructive-ghost" size="sm" disabled={busy}>
                                    <TrashIcon aria-hidden="true" />
                                    Remove
                                </Button>
                            }
                            title="Remove the sidebar logo?"
                            description="The sidebar shows the organization initials until a new logo is uploaded."
                            confirmLabel="Remove logo"
                            errorFallback="Couldn't remove the logo. Try again."
                            onConfirm={handleRemove}
                        />
                    ) : null}
                </div>
            </div>
            {error ? (
                <p role="alert" className="text-destructive text-sm">
                    {error}
                </p>
            ) : null}
        </div>
    )
}
