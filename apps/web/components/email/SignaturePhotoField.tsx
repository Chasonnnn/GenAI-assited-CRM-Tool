import type { ReactNode } from "react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Label } from "@/components/ui/label"

export function SignaturePhotoField({
    signaturePhotoUrl,
    profilePhotoUrl,
    profileName,
    avatarAction,
    customPhotoAction,
}: {
    signaturePhotoUrl: string | null
    profilePhotoUrl: string | null
    profileName: string
    avatarAction: ReactNode
    customPhotoAction?: ReactNode
}) {
    const hasSignaturePhoto = Boolean(signaturePhotoUrl)
    const displayPhoto = signaturePhotoUrl || profilePhotoUrl
    const initials =
        profileName
            ?.split(" ")
            .map((name) => name[0])
            .join("")
            .toUpperCase()
            .slice(0, 2) || "??"

    return (
        <div className="space-y-3">
            <Label className="text-sm font-medium">Signature Photo</Label>
            <div className="flex items-center gap-4">
                <div className="relative group">
                    <Avatar className="size-20 border-2 border-border">
                        <AvatarImage src={displayPhoto || undefined} />
                        <AvatarFallback className="text-lg bg-muted">{initials}</AvatarFallback>
                    </Avatar>
                    {avatarAction}
                </div>
                <div className="flex-1 space-y-1">
                    {hasSignaturePhoto ? (
                        <>
                            <p className="text-sm font-medium text-primary">Custom signature photo</p>
                            <p className="text-xs text-muted-foreground">Different from your profile avatar</p>
                            {customPhotoAction}
                        </>
                    ) : (
                        <>
                            <p className="text-sm text-muted-foreground">
                                {profilePhotoUrl ? "Using profile photo" : "No photo set"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Click camera to upload a signature-specific photo
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
