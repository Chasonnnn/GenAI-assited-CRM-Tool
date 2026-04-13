"use client"

import { Suspense, use, useEffect, useState, useRef, useCallback, useMemo } from "react"
import NextImage from "next/image"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import DOMPurify from "dompurify"
import {
  CameraIcon,
  MonitorIcon,
  SmartphoneIcon,
  Loader2Icon,
  CheckIcon,
  UploadIcon,
  TrashIcon,
  PaletteIcon,
  PlusIcon,
  MailIcon,
  EyeIcon,
  LinkIcon,
  LightbulbIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getOrgSettings, updateProfile, updateOrgSettings } from "@/lib/api/settings"
import {
  useOrgSignature,
  useUpdateOrgSignature,
  useUploadOrgLogo,
  useDeleteOrgLogo,
} from "@/lib/hooks/use-signature"
import {
  useSessions,
  useRevokeSession,
  useRevokeAllSessions,
  useUploadAvatar,
  useDeleteAvatar,
} from "@/lib/hooks/use-sessions"
import { useSystemHealth } from "@/lib/hooks/use-system"
import type { SocialLink } from "@/lib/api/signature"
import { toast } from "sonner"
import { getOrgSignaturePreview } from "@/lib/api/signature"
import { SafeHtmlContent } from "@/components/safe-html-content"
import { IntelligentSuggestionsSection } from "./intelligent-suggestions-section"

const ROLE_LABELS: Record<string, string> = {
  intake_specialist: "Intake Specialist",
  case_manager: "Case Manager",
  admin: "Admin",
  developer: "Developer",
}

type ProfileFormState = {
  name: string
  phone: string
  title: string
}

type OrgBrandingFormState = {
  template: string
  primaryColor: string
  companyName: string
  address: string
  phone: string
  website: string
  disclaimer: string
  orgEmail: string
}

type OrgBrandingUiState = {
  saved: boolean
  saving: boolean
  previewLoading: boolean
  previewHtml: string | null
  orgSettingsLoading: boolean
  orgSettingsError: string | null
  initialized: boolean
}

type OrgDefaultsState = {
  name: string
  address: string
  phone: string
}

type SignatureTemplateOption = {
  id: string
  name: string
  description: string
}

type SettingsTab = "general" | "email-signature" | "intelligent-suggestions"

type SettingsPageSearchParams = Promise<Record<string, string | string[] | undefined>>

function normalizeSettingsTab(tabParam: string | string[] | undefined, isAdmin: boolean): SettingsTab {
  const tab = Array.isArray(tabParam) ? tabParam[0] : tabParam
  return isAdmin && (tab === "email-signature" || tab === "intelligent-suggestions")
    ? tab
    : "general"
}

function toUrlSearchParams(searchParams: Record<string, string | string[] | undefined>): URLSearchParams {
  const nextParams = new URLSearchParams()
  for (const [key, value] of Object.entries(searchParams)) {
    if (typeof value === "string") {
      nextParams.set(key, value)
      continue
    }
    for (const item of value ?? []) {
      nextParams.append(key, item)
    }
  }
  return nextParams
}

function SignatureTemplatePicker({
  templates,
  selectedTemplate,
  onSelect,
}: {
  templates: SignatureTemplateOption[]
  selectedTemplate: string
  onSelect: (templateId: string) => void
}) {
  return (
    <div className="space-y-3">
      <Label>Signature Template</Label>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5" role="radiogroup" aria-label="Signature template">
        {templates.map((templateOption) => (
          <button
            key={templateOption.id}
            type="button"
            onClick={() => onSelect(templateOption.id)}
            aria-pressed={selectedTemplate === templateOption.id}
            aria-label={`Template ${templateOption.name}`}
            className={`rounded-lg border p-3 text-left transition-colors ${
              selectedTemplate === templateOption.id
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground"
            }`}
          >
            <div className="text-sm font-medium">{templateOption.name}</div>
            <div className="text-xs text-muted-foreground">{templateOption.description}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

function OrganizationLogoField({
  logoUrl,
  fileInputRef,
  onUpload,
  onDelete,
  uploadPending,
  deletePending,
}: {
  logoUrl?: string | null
  fileInputRef: React.RefObject<HTMLInputElement | null>
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void
  onDelete: () => void
  uploadPending: boolean
  deletePending: boolean
}) {
  return (
    <div className="space-y-3">
      <Label>Organization Logo</Label>
      <div className="flex items-center gap-4">
        {logoUrl ? (
          <div className="group relative">
            <NextImage
              src={logoUrl}
              alt="Organization Logo"
              width={200}
              height={80}
              unoptimized
              className="h-16 w-auto rounded border"
            />
            <button
              type="button"
              onClick={onDelete}
              disabled={deletePending}
              className="absolute -right-2 -top-2 rounded-full bg-destructive p-1 text-destructive-foreground opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
              aria-label="Remove organization logo"
            >
              <TrashIcon className="size-3" aria-hidden="true" />
            </button>
          </div>
        ) : (
          <div className="flex h-16 w-32 items-center justify-center rounded border-2 border-dashed text-muted-foreground">
            No logo
          </div>
        )}
        <div>
          <input
            id="org-logo-upload"
            name="org_logo_upload"
            type="file"
            ref={fileInputRef}
            onChange={onUpload}
            accept="image/png,image/jpeg"
            className="hidden"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadPending}
          >
            {uploadPending ? (
              <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
              <UploadIcon className="mr-2 size-4" aria-hidden="true" />
            )}
            Upload Logo
          </Button>
          <p className="mt-1 text-xs text-muted-foreground">Max 200x80px, PNG/JPG</p>
        </div>
      </div>
    </div>
  )
}

function SignaturePreviewPanel({ html }: { html: string }) {
  return (
    <div className="rounded-lg border border-border bg-white p-6">
      <p className="mb-3 border-b pb-3 text-xs text-muted-foreground">
        Preview with sample employee data:
      </p>
      <SafeHtmlContent
        html={html}
        className="prose prose-sm prose-stone max-w-none text-stone-900"
      />
    </div>
  )
}

function OrganizationBrandingFields({
  brandingForm,
  orgSettingsError,
  onFieldChange,
}: {
  brandingForm: OrgBrandingFormState
  orgSettingsError: string | null
  onFieldChange: <K extends keyof OrgBrandingFormState>(field: K, value: OrgBrandingFormState[K]) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="primaryColor">Primary Color</Label>
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="color"
              id="primaryColor"
              value={brandingForm.primaryColor}
              onChange={(event) => onFieldChange("primaryColor", event.target.value)}
              className="w-10 h-10 rounded cursor-pointer border"
            />
          </div>
          <Input
            value={brandingForm.primaryColor}
            onChange={(event) => onFieldChange("primaryColor", event.target.value)}
            className="w-28 font-mono text-sm"
            placeholder="#E444A4"
            name="primaryColorHex"
            autoComplete="off"
            aria-label="Primary color hex"
          />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="sigCompanyName">Organization Name</Label>
          <Input
            id="sigCompanyName"
            name="sigCompanyName"
            autoComplete="organization"
            value={brandingForm.companyName}
            onChange={(event) => onFieldChange("companyName", event.target.value)}
            placeholder="Your Organization"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigWebsite">Website</Label>
          <Input
            id="sigWebsite"
            name="sigWebsite"
            autoComplete="url"
            value={brandingForm.website}
            onChange={(event) => onFieldChange("website", event.target.value)}
            placeholder="https://www.example.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigPhone">Phone</Label>
          <Input
            id="sigPhone"
            name="sigPhone"
            autoComplete="tel"
            value={brandingForm.phone}
            onChange={(event) => onFieldChange("phone", event.target.value)}
            placeholder="(555) 123-4567"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigEmail">Email</Label>
          <Input
            id="sigEmail"
            name="sigEmail"
            autoComplete="email"
            type="email"
            value={brandingForm.orgEmail}
            onChange={(event) => onFieldChange("orgEmail", event.target.value)}
            placeholder="contact@company.com"
            disabled={!!orgSettingsError}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="sigAddress">Address</Label>
          <Textarea
            id="sigAddress"
            name="sigAddress"
            autoComplete="street-address"
            value={brandingForm.address}
            onChange={(event) => onFieldChange("address", event.target.value)}
            placeholder="123 Main St, City, State 12345"
            rows={2}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="sigDisclaimer">Disclaimer / Legal Footer</Label>
          <Textarea
            id="sigDisclaimer"
            name="sigDisclaimer"
            value={brandingForm.disclaimer}
            onChange={(event) => onFieldChange("disclaimer", event.target.value)}
            placeholder="Confidentiality notice, legal disclaimer, etc."
            rows={3}
          />
          <p className="text-xs text-muted-foreground">
            Appears at the bottom of all email signatures (optional)
          </p>
        </div>
      </div>
    </>
  )
}

function OrganizationBrandingActions({
  previewLoading,
  saving,
  saved,
  previewHtml,
  onPreview,
  onSave,
  saveDisabled,
}: {
  previewLoading: boolean
  saving: boolean
  saved: boolean
  previewHtml: string | null
  onPreview: () => Promise<void>
  onSave: () => Promise<void>
  saveDisabled: boolean
}) {
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={onPreview}
          disabled={previewLoading}
        >
          {previewLoading ? (
            <>
              <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Loading…
            </>
          ) : (
            <>
              <EyeIcon className="mr-2 size-4" aria-hidden="true" /> Preview Template
            </>
          )}
        </Button>
        <Button onClick={onSave} disabled={saveDisabled}>
          {saving ? (
            <>
              <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Saving…
            </>
          ) : saved ? (
            <>
              <CheckIcon className="mr-2 size-4" aria-hidden="true" /> Saved!
            </>
          ) : (
            "Save Organization Branding"
          )}
        </Button>
      </div>

      {previewHtml && (
        <SignaturePreviewPanel html={previewHtml} />
      )}
    </div>
  )
}

// =============================================================================
// Profile Section with Avatar Upload, Phone, Title
// =============================================================================

function ProfileSection() {
  const { user, refetch } = useAuth()
  const uploadAvatarMutation = useUploadAvatar()
  const deleteAvatarMutation = useDeleteAvatar()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [profileForm, setProfileForm] = useState<ProfileFormState>({
    name: user?.display_name || "",
    phone: user?.phone || "",
    title: user?.title || "",
  })
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileSaved, setProfileSaved] = useState(false)
  const userDisplayName = user?.display_name || ""
  const userPhone = user?.phone || ""
  const userTitle = user?.title || ""

  useEffect(() => {
    setProfileForm((current) => {
      if (
        current.name === userDisplayName
        && current.phone === userPhone
        && current.title === userTitle
      ) {
        return current
      }
      return {
        name: userDisplayName,
        phone: userPhone,
        title: userTitle,
      }
    })
  }, [userDisplayName, userPhone, userTitle])

  const updateProfileForm = (field: keyof ProfileFormState, value: string) => {
    setProfileForm((current) => ({ ...current, [field]: value }))
  }

  const initials =
    user?.display_name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "??"

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const allowedTypes = ["image/png", "image/jpeg", "image/webp"]
    if (!allowedTypes.includes(file.type)) {
      toast.error("Please select a PNG, JPEG, or WebP image")
      return
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      toast.error("Image must be less than 2MB")
      return
    }

    uploadAvatarMutation.mutate(file, {
      onSuccess: () => refetch(),
    })
  }

  const handleDeleteAvatar = () => {
    if (confirm("Remove your profile photo?")) {
      deleteAvatarMutation.mutate(undefined, {
        onSuccess: () => refetch(),
      })
    }
  }

  const handleSaveProfile = async () => {
    setProfileSaving(true)
    try {
      const trimmedName = profileForm.name.trim()
      const trimmedPhone = profileForm.phone.trim()
      const trimmedTitle = profileForm.title.trim()
      await updateProfile({
        ...(trimmedName ? { display_name: trimmedName } : {}),
        ...(trimmedPhone ? { phone: trimmedPhone } : {}),
        ...(trimmedTitle ? { title: trimmedTitle } : {}),
      })
      setProfileSaved(true)
      setTimeout(() => setProfileSaved(false), 2000)
      refetch()
    } catch (error) {
      console.error("Failed to save profile:", error)
    } finally {
      setProfileSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="relative group">
          <Avatar className="size-20">
            <AvatarImage src={user?.avatar_url} />
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <input
            id="profile-avatar-upload"
            name="profile_avatar_upload"
            type="file"
            ref={fileInputRef}
            onChange={handleAvatarUpload}
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadAvatarMutation.isPending}
            className="absolute bottom-0 right-0 flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            aria-label="Upload profile photo"
          >
            {uploadAvatarMutation.isPending ? (
              <Loader2Icon className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
              <CameraIcon className="size-3.5" aria-hidden="true" />
            )}
          </button>
          {user?.avatar_url && (
          <button
            type="button"
            onClick={handleDeleteAvatar}
            disabled={deleteAvatarMutation.isPending}
            className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
            aria-label="Remove profile photo"
          >
              <TrashIcon className="size-3" aria-hidden="true" />
            </button>
          )}
        </div>
        <div>
          <h3 className="font-medium">Profile</h3>
          <p className="text-sm text-muted-foreground">Managed via Google SSO</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="fullName">Full Name</Label>
          <Input
            id="fullName"
            name="fullName"
            autoComplete="name"
            value={profileForm.name}
            onChange={(e) => updateProfileForm("name", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            autoComplete="email"
            type="email"
            defaultValue={user?.email || ""}
            disabled
          />
          <p className="text-xs text-muted-foreground">Email is managed by SSO</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
            name="title"
            autoComplete="organization-title"
            value={profileForm.title}
            onChange={(e) => updateProfileForm("title", e.target.value)}
            placeholder="Case Manager"
          />
          <p className="text-xs text-muted-foreground">Displayed in email signatures</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="phone">Phone</Label>
          <Input
            id="phone"
            name="phone"
            autoComplete="tel"
            type="tel"
            value={profileForm.phone}
            onChange={(e) => updateProfileForm("phone", e.target.value)}
            placeholder="(555) 123-4567"
          />
          <p className="text-xs text-muted-foreground">Displayed in email signatures</p>
        </div>

        <div className="space-y-2">
          <Label>Role</Label>
          <div>
            <Badge className="bg-primary/10 text-primary border-primary/20">
              {ROLE_LABELS[user?.role ?? ""] || "Unknown"}
            </Badge>
          </div>
        </div>
      </div>

      <Button onClick={handleSaveProfile} disabled={profileSaving}>
        {profileSaving ? (
          <>
            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Saving…
          </>
        ) : profileSaved ? (
          <>
            <CheckIcon className="mr-2 size-4" aria-hidden="true" /> Saved!
          </>
        ) : (
          "Save Changes"
        )}
      </Button>
    </div>
  )
}

// =============================================================================
// Active Sessions Section (Real API)
// =============================================================================

function ActiveSessionsSection() {
  const { data: sessions, isLoading } = useSessions()
  const revokeSession = useRevokeSession()
  const revokeAllSessions = useRevokeAllSessions()

  const handleRevokeSession = (sessionId: string) => {
    if (confirm("Revoke this session? The device will be logged out.")) {
      revokeSession.mutate(sessionId)
    }
  }

  const handleRevokeAllSessions = () => {
    if (confirm("Log out from all other devices?")) {
      revokeAllSessions.mutate()
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const getDeviceIcon = (deviceInfo: string | null) => {
    const info = deviceInfo?.toLowerCase() || ""
    if (info.includes("mobile") || info.includes("android") || info.includes("iphone")) {
      return <SmartphoneIcon className="mt-0.5 size-5 text-muted-foreground" aria-hidden="true" />
    }
    return <MonitorIcon className="mt-0.5 size-5 text-muted-foreground" aria-hidden="true" />
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <h4 className="font-medium">Active Sessions</h4>
        <div className="flex items-center justify-center py-8">
          <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
        </div>
      </div>
    )
  }

  const otherSessions = sessions?.filter((s) => !s.is_current) || []

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-medium">Active Sessions</h4>
        {otherSessions.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRevokeAllSessions}
            disabled={revokeAllSessions.isPending}
            className="text-destructive hover:text-destructive"
          >
            {revokeAllSessions.isPending ? (
              <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : null}
            Log out all others
          </Button>
        )}
      </div>

      {sessions?.map((session) => (
        <div
          key={session.id}
          className="flex items-start justify-between rounded-lg border border-border p-4"
        >
          <div className="flex gap-3">
            {getDeviceIcon(session.device_info)}
            <div>
              <p className="font-medium">
                {session.device_info || "Unknown device"}
                {session.is_current && (
                  <span className="ml-2 text-xs text-muted-foreground">(this device)</span>
                )}
              </p>
              <p className="text-sm text-muted-foreground">
                {session.ip_address || "Unknown IP"} &middot; Last active{" "}
                {formatDate(session.last_active_at)}
              </p>
            </div>
          </div>
          {session.is_current ? (
            <Badge className="bg-green-500/10 text-green-500 border-green-500/20">Current</Badge>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleRevokeSession(session.id)}
              disabled={revokeSession.isPending}
            >
              {revokeSession.isPending ? (
                <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : (
                "Revoke"
              )}
            </Button>
          )}
        </div>
      ))}

      {(!sessions || sessions.length === 0) && (
        <div className="rounded-lg border border-border p-4 text-center text-muted-foreground">
          No active sessions found
        </div>
      )}
    </div>
  )
}

// =============================================================================
// App Version
// =============================================================================

function AppVersion() {
  const { data } = useSystemHealth()
  const versionLabel = data?.version ? `v${data.version}` : "—"

  return (
    <p className="text-xs text-muted-foreground">{versionLabel}</p>
  )
}

// =============================================================================
// Social Links Section
// =============================================================================

function SocialLinksSection() {
  const { data: orgSig, isLoading } = useOrgSignature()
  const updateOrgSig = useUpdateOrgSignature()

  const [links, setLinks] = useState<SocialLink[]>([])
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (orgSig?.signature_social_links) {
      setLinks(orgSig.signature_social_links)
    }
  }, [orgSig])

  const addLink = () => {
    if (links.length >= 6) {
      toast.error("Maximum 6 social links allowed")
      return
    }
    setLinks([...links, { platform: "", url: "" }])
  }

  const removeLink = (index: number) => {
    setLinks(links.filter((_, i) => i !== index))
  }

  const updateLink = (index: number, field: keyof SocialLink, value: string) => {
    const newLinks = [...links]
    const current = newLinks[index]
    if (!current) return
    newLinks[index] = { ...current, [field]: value }
    setLinks(newLinks)
  }

  const handleSave = async () => {
    // Filter out empty links
    const validLinks = links.filter((l) => l.platform.trim() && l.url.trim())

    // Validate URLs
    for (const link of validLinks) {
      if (!link.url.startsWith("https://")) {
        toast.error(`URL must start with https:// (${link.platform})`)
        return
      }
    }

    await updateOrgSig.mutateAsync({
      signature_social_links: validLinks.length > 0 ? validLinks : null,
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse motion-reduce:animate-none flex gap-4">
          <div className="h-24 w-full bg-muted rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium flex items-center gap-2">
          <LinkIcon className="size-4" aria-hidden="true" />
          Social Links
        </h3>
        <p className="text-sm text-muted-foreground">
          Social media links shown in email signatures (max 6)
        </p>
      </div>

      <div className="space-y-3">
        {links.map((link, i) => {
          const linkOccurrence = links
            .slice(0, i + 1)
            .filter((candidate) => candidate.platform === link.platform && candidate.url === link.url).length
          const linkKey = `${link.platform}-${link.url}-${linkOccurrence}`
          return (
            <div key={linkKey} className="flex items-center gap-3">
              <Input
                value={link.platform}
                onChange={(e) => updateLink(i, "platform", e.target.value)}
                placeholder="Platform (e.g., LinkedIn)"
                className="w-40"
                name={`social-platform-${i}`}
                autoComplete="off"
                aria-label={`Social platform ${i + 1}`}
              />
              <Input
                value={link.url}
                onChange={(e) => updateLink(i, "url", e.target.value)}
                placeholder="https://…"
                className="flex-1"
                name={`social-url-${i}`}
                autoComplete="url"
                aria-label={`Social URL ${i + 1}`}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeLink(i)}
                className="text-destructive hover:text-destructive"
                aria-label={`Remove social link ${i + 1}`}
              >
                <TrashIcon className="size-4" aria-hidden="true" />
              </Button>
            </div>
          )
        })}

        {links.length < 6 && (
          <Button type="button" variant="outline" size="sm" onClick={addLink}>
            <PlusIcon className="mr-2 size-4" aria-hidden="true" />
            Add Social Link
          </Button>
        )}
      </div>

      <Button onClick={handleSave} disabled={updateOrgSig.isPending}>
        {updateOrgSig.isPending ? (
          <>
            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Saving…
          </>
        ) : saved ? (
          <>
            <CheckIcon className="mr-2 size-4" aria-hidden="true" /> Saved!
          </>
        ) : (
          "Save Social Links"
        )}
      </Button>
    </div>
  )
}

// =============================================================================
// Organization Branding Section
// =============================================================================

function OrganizationBrandingSection() {
  const { user, refetch } = useAuth()
  const { data: orgSig, isLoading: sigLoading } = useOrgSignature()
  const updateOrgSig = useUpdateOrgSignature()
  const uploadLogo = useUploadOrgLogo()
  const deleteLogo = useDeleteOrgLogo()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [brandingForm, setBrandingForm] = useState<OrgBrandingFormState>({
    template: "",
    primaryColor: "#E444A4",
    companyName: "",
    address: "",
    phone: "",
    website: "",
    disclaimer: "",
    orgEmail: "",
  })
  const [brandingUi, setBrandingUi] = useState<OrgBrandingUiState>({
    saved: false,
    saving: false,
    previewLoading: false,
    previewHtml: null,
    orgSettingsLoading: true,
    orgSettingsError: null,
    initialized: false,
  })
  const [orgDefaults, setOrgDefaults] = useState<OrgDefaultsState>({ name: "", address: "", phone: "" })

  const sanitizedPreviewHtml = useMemo(
    () => (brandingUi.previewHtml ? DOMPurify.sanitize(brandingUi.previewHtml) : null),
    [brandingUi.previewHtml]
  )

  const isMountedRef = useRef(true)

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const loadOrgSettings = useCallback(async () => {
    if (!user?.org_id) return
    setBrandingUi((current) => ({
      ...current,
      orgSettingsLoading: true,
      orgSettingsError: null,
    }))
    try {
      const settings = await getOrgSettings()
      if (!isMountedRef.current) return
      setOrgDefaults({
        name: settings.name || "",
        address: settings.address || "",
        phone: settings.phone || "",
      })
      setBrandingForm((current) => ({ ...current, orgEmail: settings.email || "" }))
    } catch (error) {
      console.error("Failed to load organization settings:", error)
      if (!isMountedRef.current) return
      setBrandingUi((current) => ({
        ...current,
        orgSettingsError: "Unable to load organization settings. Please retry.",
      }))
    } finally {
      if (isMountedRef.current) {
        setBrandingUi((current) => ({ ...current, orgSettingsLoading: false }))
      }
    }
  }, [user?.org_id])

  useEffect(() => {
    if (user?.org_id) {
      loadOrgSettings()
    } else {
      setBrandingUi((current) => ({ ...current, orgSettingsLoading: false }))
    }
  }, [user?.org_id, loadOrgSettings])

  useEffect(() => {
    if (brandingUi.initialized) return
    if (sigLoading || brandingUi.orgSettingsLoading) return
    setBrandingForm((current) => ({
      ...current,
      template: orgSig?.signature_template || "classic",
      primaryColor: orgSig?.signature_primary_color || "#E444A4",
      companyName: orgSig?.signature_company_name || orgDefaults.name || user?.org_name || "",
      address: orgSig?.signature_address || orgDefaults.address || "",
      phone: orgSig?.signature_phone || orgDefaults.phone || "",
      website: orgSig?.signature_website || "",
      disclaimer: orgSig?.signature_disclaimer || "",
    }))
    setBrandingUi((current) => ({ ...current, initialized: true }))
  }, [brandingUi.initialized, sigLoading, brandingUi.orgSettingsLoading, orgSig, orgDefaults, user?.org_name])

  const updateBrandingForm = <K extends keyof OrgBrandingFormState>(field: K, value: OrgBrandingFormState[K]) => {
    setBrandingForm((current) => ({ ...current, [field]: value }))
  }

  const handleSave = async () => {
    setBrandingUi((current) => ({ ...current, saving: true }))
    try {
      const trimmedCompanyName = brandingForm.companyName.trim()
      const trimmedAddress = brandingForm.address.trim()
      const trimmedPhone = brandingForm.phone.trim()
      const trimmedWebsite = brandingForm.website.trim()
      const trimmedDisclaimer = brandingForm.disclaimer.trim()
      const trimmedEmail = brandingForm.orgEmail.trim()

      const signaturePayload = {
        signature_template: brandingForm.template,
        signature_primary_color: brandingForm.primaryColor,
        signature_company_name: trimmedCompanyName || null,
        signature_address: trimmedAddress || null,
        signature_phone: trimmedPhone || null,
        signature_website: trimmedWebsite || null,
        signature_disclaimer: trimmedDisclaimer || null,
      }

      if (brandingUi.orgSettingsError) {
        await updateOrgSig.mutateAsync(signaturePayload)
      } else {
        await Promise.all([
          updateOrgSig.mutateAsync(signaturePayload),
          updateOrgSettings({
            ...(trimmedCompanyName ? { name: trimmedCompanyName } : {}),
            ...(trimmedAddress ? { address: trimmedAddress } : {}),
            ...(trimmedPhone ? { phone: trimmedPhone } : {}),
            ...(trimmedEmail ? { email: trimmedEmail } : {}),
          }),
        ])
        refetch()
      }

      setBrandingUi((current) => ({ ...current, saved: true }))
      setTimeout(() => {
        setBrandingUi((current) => ({ ...current, saved: false }))
      }, 2000)
    } catch (error) {
      console.error("Failed to save organization branding:", error)
      toast.error("Failed to save organization branding")
    } finally {
      setBrandingUi((current) => ({ ...current, saving: false }))
    }
  }

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const allowedTypes = ["image/png", "image/jpeg"]
      if (!allowedTypes.includes(file.type)) {
        toast.error("Logo must be a PNG or JPEG file")
        return
      }
      if (file.size > 1024 * 1024) {
        toast.error("Logo must be less than 1MB")
        return
      }
      uploadLogo.mutate(file)
    }
  }

  const handleDeleteLogo = () => {
    if (confirm("Delete organization logo?")) {
      deleteLogo.mutate()
    }
  }

  const handlePreviewTemplate = async () => {
    setBrandingUi((current) => ({ ...current, previewLoading: true }))
    try {
      const result = await getOrgSignaturePreview(brandingForm.template)
      setBrandingUi((current) => ({ ...current, previewHtml: result.html }))
    } catch {
      // Silent fail
    } finally {
      setBrandingUi((current) => ({ ...current, previewLoading: false }))
    }
  }

  if (sigLoading || brandingUi.orgSettingsLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse motion-reduce:animate-none flex gap-4">
          <div className="h-24 w-full bg-muted rounded" />
        </div>
      </div>
    )
  }

  const templates: SignatureTemplateOption[] = orgSig?.available_templates || [
    { id: "classic", name: "Classic", description: "Traditional professional layout" },
    { id: "modern", name: "Modern", description: "Clean contemporary design" },
    { id: "minimal", name: "Minimal", description: "Simple and focused" },
    { id: "professional", name: "Professional", description: "Formal business style" },
    { id: "creative", name: "Creative", description: "Bold and distinctive" },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium flex items-center gap-2">
          <PaletteIcon className="size-4" aria-hidden="true" />
          Organization Branding
        </h3>
        <p className="text-sm text-muted-foreground">
          Organization-wide branding used in email signatures
        </p>
      </div>

      {brandingUi.orgSettingsError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{brandingUi.orgSettingsError}</span>
            <Button variant="outline" onClick={loadOrgSettings}>
              Retry
            </Button>
          </div>
        </div>
      )}

      <SignatureTemplatePicker
        templates={templates}
        selectedTemplate={brandingForm.template}
        onSelect={(templateId) => updateBrandingForm("template", templateId)}
      />

      <OrganizationLogoField
        logoUrl={orgSig?.signature_logo_url ?? null}
        fileInputRef={fileInputRef}
        onUpload={handleLogoUpload}
        onDelete={handleDeleteLogo}
        uploadPending={uploadLogo.isPending}
        deletePending={deleteLogo.isPending}
      />

      <OrganizationBrandingFields
        brandingForm={brandingForm}
        orgSettingsError={brandingUi.orgSettingsError}
        onFieldChange={updateBrandingForm}
      />

      <OrganizationBrandingActions
        previewLoading={brandingUi.previewLoading}
        saving={brandingUi.saving}
        saved={brandingUi.saved}
        previewHtml={sanitizedPreviewHtml}
        onPreview={handlePreviewTemplate}
        onSave={handleSave}
        saveDisabled={brandingUi.saving || sigLoading || brandingUi.orgSettingsLoading}
      />
    </div>
  )
}

// =============================================================================
// Main Settings Page
// =============================================================================

function SettingsPageContent({ searchParams }: { searchParams: SettingsPageSearchParams }) {
  const router = useRouter()
  const { user } = useAuth()
  const resolvedSearchParams = use(searchParams)

  const isAdmin = user?.role === "admin" || user?.role === "developer"
  const activeTab = normalizeSettingsTab(resolvedSearchParams.tab, isAdmin)

  const handleTabChange = (value: string) => {
    const nextTab = normalizeSettingsTab(value, isAdmin)
    const nextParams = toUrlSearchParams(resolvedSearchParams)
    if (nextTab === "general") {
      nextParams.delete("tab")
    } else {
      nextParams.set("tab", nextTab)
    }
    const queryString = nextParams.toString()
    const nextUrl = queryString ? `/settings?${queryString}` : "/settings"
    router.replace(nextUrl, { scroll: false })
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Page Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex h-16 items-center px-6">
          <h1 className="text-2xl font-semibold">Settings</h1>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="mb-6">
            <TabsTrigger value="general">General</TabsTrigger>
            {isAdmin && (
              <TabsTrigger value="email-signature" className="flex items-center gap-2">
                <MailIcon className="size-4" aria-hidden="true" />
                Email Signature
              </TabsTrigger>
            )}
            {isAdmin && (
              <TabsTrigger value="intelligent-suggestions" className="flex items-center gap-2">
                <LightbulbIcon className="size-4" aria-hidden="true" />
                Intelligent Suggestions
              </TabsTrigger>
            )}
          </TabsList>

          {/* General Tab */}
          <TabsContent value="general">
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>General</CardTitle>
                  <CardDescription>Profile and access settings</CardDescription>
                </CardHeader>
                <CardContent className="space-y-10">
                  {/* Profile Section */}
                  <ProfileSection />

                  <div className="border-t border-border" />

                  {/* Access Section */}
                  <div className="space-y-6">
                    <div>
                      <h3 className="font-medium">Access</h3>
                      <p className="text-sm text-muted-foreground">2FA and session controls</p>
                    </div>

                    <div className="flex items-center justify-between rounded-lg border border-border p-4">
                      <div className="space-y-0.5">
                        <Label htmlFor="twoFactor">Two-factor authentication</Label>
                        <p className="text-sm text-muted-foreground">Managed by Google Workspace + Duo</p>
                      </div>
                      <Switch id="twoFactor" checked disabled />
                    </div>

                    {/* Real Sessions */}
                    <ActiveSessionsSection />

                    <div className="flex items-center justify-between">
                      <p className="text-xs text-muted-foreground">
                        Account deletion is managed by your organization admin.
                      </p>
                      <AppVersion />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Email Signature Tab (Admin only) */}
          {isAdmin && (
            <TabsContent value="email-signature">
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <MailIcon className="size-5" aria-hidden="true" />
                      Email Signature Settings
                    </CardTitle>
                    <CardDescription>
                      Organization-wide email signature configuration. These settings apply to all users.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-10">
                    {/* Organization Branding (includes preview) */}
                    <OrganizationBrandingSection />

                    <div className="border-t border-border" />

                    {/* Social Links */}
                    <SocialLinksSection />
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          )}

          {isAdmin && (
            <TabsContent value="intelligent-suggestions">
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <LightbulbIcon className="size-5" aria-hidden="true" />
                      Intelligent Suggestion Rules
                    </CardTitle>
                    <CardDescription>
                      Configure org-wide intelligent suggestion thresholds and digest behavior.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <IntelligentSuggestionsSection />
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          )}
        </Tabs>
      </div>
    </div>
  )
}

export default function SettingsPage({
  searchParams,
}: {
  searchParams?: SettingsPageSearchParams
}) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <SettingsPageContent searchParams={searchParams ?? Promise.resolve({})} />
    </Suspense>
  )
}
