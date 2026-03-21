"use client"

import { Suspense, useEffect, useState, useRef, useCallback, useMemo } from "react"
import NextImage from "next/image"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
import {
  createIntelligentSuggestionRule,
  deleteIntelligentSuggestionRule,
  getIntelligentSuggestionRules,
  getIntelligentSuggestionSettings,
  getIntelligentSuggestionTemplates,
  getOrgSettings,
  updateIntelligentSuggestionRule,
  updateIntelligentSuggestionSettings,
  updateProfile,
  updateOrgSettings,
  type IntelligentSuggestionRule,
  type IntelligentSuggestionSettings,
  type IntelligentSuggestionTemplate,
} from "@/lib/api/settings"
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
import { usePipelines } from "@/lib/hooks/use-pipelines"
import { useSystemHealth } from "@/lib/hooks/use-system"
import type { SocialLink } from "@/lib/api/signature"
import { toast } from "sonner"
import { getOrgSignaturePreview } from "@/lib/api/signature"
import { SafeHtmlContent } from "@/components/safe-html-content"

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
              className="absolute -right-2 -top-2 rounded-full bg-destructive p-1 text-destructive-foreground opacity-0 transition-opacity group-hover:opacity-100"
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

  useEffect(() => {
    if (user) {
      setProfileForm({
        name: user.display_name || "",
        phone: user.phone || "",
        title: user.title || "",
      })
    }
  }, [user])

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
              className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground opacity-0 group-hover:opacity-100 transition-opacity"
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

      {/* Primary Color */}
      <div className="space-y-2">
        <Label htmlFor="primaryColor">Primary Color</Label>
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="color"
              id="primaryColor"
              value={brandingForm.primaryColor}
              onChange={(e) => updateBrandingForm("primaryColor", e.target.value)}
              className="w-10 h-10 rounded cursor-pointer border"
            />
          </div>
          <Input
            value={brandingForm.primaryColor}
            onChange={(e) => updateBrandingForm("primaryColor", e.target.value)}
            className="w-28 font-mono text-sm"
            placeholder="#E444A4"
            name="primaryColorHex"
            autoComplete="off"
            aria-label="Primary color hex"
          />
        </div>
      </div>

      {/* Organization Info */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="sigCompanyName">Organization Name</Label>
          <Input
            id="sigCompanyName"
            name="sigCompanyName"
            autoComplete="organization"
            value={brandingForm.companyName}
            onChange={(e) => updateBrandingForm("companyName", e.target.value)}
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
            onChange={(e) => updateBrandingForm("website", e.target.value)}
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
            onChange={(e) => updateBrandingForm("phone", e.target.value)}
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
            onChange={(e) => updateBrandingForm("orgEmail", e.target.value)}
            placeholder="contact@company.com"
            disabled={!!brandingUi.orgSettingsError}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="sigAddress">Address</Label>
          <Textarea
            id="sigAddress"
            name="sigAddress"
            autoComplete="street-address"
            value={brandingForm.address}
            onChange={(e) => updateBrandingForm("address", e.target.value)}
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
            onChange={(e) => updateBrandingForm("disclaimer", e.target.value)}
            placeholder="Confidentiality notice, legal disclaimer, etc."
            rows={3}
          />
          <p className="text-xs text-muted-foreground">
            Appears at the bottom of all email signatures (optional)
          </p>
        </div>
      </div>

      {/* Preview Button */}
      <div className="space-y-4">
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handlePreviewTemplate}
            disabled={brandingUi.previewLoading}
          >
            {brandingUi.previewLoading ? (
              <>
                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Loading…
              </>
            ) : (
              <>
                <EyeIcon className="mr-2 size-4" aria-hidden="true" /> Preview Template
              </>
            )}
          </Button>
          <Button onClick={handleSave} disabled={brandingUi.saving || sigLoading || brandingUi.orgSettingsLoading}>
            {brandingUi.saving ? (
              <>
                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Saving…
              </>
            ) : brandingUi.saved ? (
              <>
                <CheckIcon className="mr-2 size-4" aria-hidden="true" /> Saved!
              </>
            ) : (
              "Save Organization Branding"
            )}
          </Button>
        </div>

        {sanitizedPreviewHtml && (
          <SignaturePreviewPanel html={sanitizedPreviewHtml} />
        )}
      </div>
    </div>
  )
}

function IntelligentSuggestionsSection() {
  type RuleDraft = {
    template_key: string
    name: string
    stage_slug: string
    business_days: number
    enabled: boolean
    sort_order: number
  }

  const [settings, setSettings] = useState<IntelligentSuggestionSettings | null>(null)
  const [templates, setTemplates] = useState<IntelligentSuggestionTemplate[]>([])
  const [rules, setRules] = useState<IntelligentSuggestionRule[]>([])
  const [newRuleDraft, setNewRuleDraft] = useState<RuleDraft | null>(null)
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null)
  const [editingRuleDraft, setEditingRuleDraft] = useState<RuleDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [ruleSaving, setRuleSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { data: pipelines } = usePipelines()

  const stageOptions = useMemo(() => {
    const byValue = new Map<string, { value: string; slug: string; stageKey: string; label: string }>()
    for (const pipeline of pipelines ?? []) {
      for (const rawStage of pipeline.stages ?? []) {
        const stage = rawStage as {
          slug?: string
          status?: string
          stage_key?: string
          label?: string
          is_active?: boolean
        }
        const slug = stage.slug ?? stage.status
        const stageKey = stage.stage_key ?? slug
        if (!slug || !stageKey || stage.is_active === false) continue
        if (!byValue.has(stageKey)) {
          byValue.set(stageKey, {
            value: stageKey,
            slug,
            stageKey,
            label: stage.label ?? stageKey,
          })
        }
      }
    }
    return Array.from(byValue.values())
      .sort((left, right) => left.label.localeCompare(right.label))
  }, [pipelines])

  const stageLabelByRef = useMemo(
    () =>
      new Map(
        stageOptions.flatMap((option) => [
          [option.value, option.label] as const,
          [option.slug, option.label] as const,
        ]),
      ),
    [stageOptions],
  )
  const stageOptionByValue = useMemo(
    () => new Map(stageOptions.map((option) => [option.value, option])),
    [stageOptions],
  )
  const templateByKey = useMemo(
    () => new Map(templates.map((template) => [template.template_key, template])),
    [templates],
  )

  const formatStageLabel = useCallback(
    (stageRef: string | null | undefined) => {
      if (!stageRef) return "N/A"
      return stageLabelByRef.get(stageRef) ?? stageRef.replaceAll("_", " ")
    },
    [stageLabelByRef],
  )

  const requiresStageSelection = useCallback((template: IntelligentSuggestionTemplate | undefined) => {
    if (!template) return false
    return template.rule_kind === "stage_inactivity" && template.template_key !== "preapproval_stuck"
  }, [])

  const resolveStageSlug = useCallback(
    (template: IntelligentSuggestionTemplate | undefined, stageSlug: string | null | undefined) => {
      if (!template || !requiresStageSelection(template)) return ""
      const normalized = (stageSlug ?? "").trim()
      if (normalized) {
        const matchingOption = stageOptions.find(
          (option) => option.value === normalized || option.slug === normalized,
        )
        if (matchingOption) {
          return matchingOption.value
        }
      }
      const defaultStage = (template.default_stage_key ?? template.default_stage_slug ?? "").trim()
      if (defaultStage) {
        const matchingDefault = stageOptions.find(
          (option) => option.value === defaultStage || option.slug === defaultStage,
        )
        if (matchingDefault) {
          return matchingDefault.value
        }
      }
      return stageOptions[0]?.value ?? defaultStage
    },
    [requiresStageSelection, stageOptions],
  )

  const buildRuleDraft = useCallback(
    (
      template: IntelligentSuggestionTemplate | undefined,
      sortOrder: number,
      overrides: Partial<RuleDraft> = {},
    ): RuleDraft | null => {
      if (!template) return null
      return {
        template_key: template.template_key,
        name: overrides.name ?? template.name,
        stage_slug: resolveStageSlug(
          template,
          overrides.stage_slug ?? template.default_stage_key ?? template.default_stage_slug,
        ),
        business_days: overrides.business_days ?? template.default_business_days,
        enabled: overrides.enabled ?? true,
        sort_order: overrides.sort_order ?? sortOrder,
      }
    },
    [resolveStageSlug],
  )

  const loadSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [settingsResponse, templatesResponse, rulesResponse] = await Promise.all([
        getIntelligentSuggestionSettings(),
        getIntelligentSuggestionTemplates(),
        getIntelligentSuggestionRules(),
      ])
      setSettings(settingsResponse)
      setTemplates(templatesResponse)
      setRules(rulesResponse)
      const templateSeed = templatesResponse.find((template) => template.is_default) ?? templatesResponse[0]
      if (templateSeed) {
        const draft = buildRuleDraft(templateSeed, (rulesResponse.at(-1)?.sort_order ?? 0) + 1)
        if (draft) setNewRuleDraft(draft)
      }
    } catch (loadError) {
      console.error("Failed to load intelligent suggestion settings:", loadError)
      setError("Unable to load settings. Please retry.")
    } finally {
      setLoading(false)
    }
  }, [buildRuleDraft])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  useEffect(() => {
    if (!newRuleDraft || templates.length === 0) return
    const template = templateByKey.get(newRuleDraft.template_key)
    if (!requiresStageSelection(template)) return
    const normalizedStage = resolveStageSlug(template, newRuleDraft.stage_slug)
    if (normalizedStage && normalizedStage !== newRuleDraft.stage_slug) {
      setNewRuleDraft((prev) => (prev ? { ...prev, stage_slug: normalizedStage } : prev))
    }
  }, [newRuleDraft, templateByKey, templates, requiresStageSelection, resolveStageSlug])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
      </div>
    )
  }

  if (!settings) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-destructive">{error ?? "Unable to load settings."}</p>
        <Button variant="outline" onClick={loadSettings}>
          Retry
        </Button>
      </div>
    )
  }

  const setDigestField = (rawValue: string) => {
    const parsed = Number.parseInt(rawValue, 10)
    const normalized = Number.isFinite(parsed) ? parsed : settings.digest_hour_local
    setSettings((prev) => (prev ? { ...prev, digest_hour_local: Math.max(0, Math.min(23, normalized)) } : prev))
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const updated = await updateIntelligentSuggestionSettings(settings)
      setSettings(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      toast.success("Intelligent suggestion settings updated")
    } catch (saveError) {
      console.error("Failed to save intelligent suggestion settings:", saveError)
      setError("Unable to save settings. Please try again.")
      toast.error("Failed to save intelligent suggestion settings")
    } finally {
      setSaving(false)
    }
  }

  const handleNewRuleTemplateChange = (templateKey: string | null) => {
    if (!templateKey) return
    const template = templateByKey.get(templateKey)
    if (!template) return
    setNewRuleDraft((prev) =>
      buildRuleDraft(template, prev?.sort_order ?? (rules.at(-1)?.sort_order ?? 0) + 1, {
        enabled: prev?.enabled ?? true,
      }),
    )
  }

  const handleCreateRule = async () => {
    if (!newRuleDraft) return
    const template = templateByKey.get(newRuleDraft.template_key)
    if (!template) {
      toast.error("Select a valid rule template")
      return
    }
    const stageSlug = requiresStageSelection(template)
      ? resolveStageSlug(template, newRuleDraft.stage_slug)
      : null
    if (requiresStageSelection(template) && !stageSlug) {
      toast.error("Select a stage for this workflow rule")
      return
    }

    setRuleSaving(true)
    try {
      const selectedStage = stageSlug ? stageOptionByValue.get(stageSlug) : null
      const createdRule = await createIntelligentSuggestionRule({
        template_key: template.template_key,
        name: newRuleDraft.name.trim() || template.name,
        stage_key: selectedStage?.stageKey ?? stageSlug,
        stage_slug: selectedStage?.slug ?? stageSlug,
        business_days: Math.max(1, Math.min(60, newRuleDraft.business_days)),
        enabled: newRuleDraft.enabled,
      })
      setRules((prev) =>
        [...prev, createdRule].sort((left, right) => left.sort_order - right.sort_order),
      )
      const resetDraft = buildRuleDraft(template, createdRule.sort_order + 1, { enabled: true })
      if (resetDraft) setNewRuleDraft(resetDraft)
      toast.success("Workflow rule created")
    } catch (ruleError) {
      console.error("Failed to create intelligent suggestion rule:", ruleError)
      toast.error("Failed to create workflow rule")
    } finally {
      setRuleSaving(false)
    }
  }

  const handleToggleRuleEnabled = async (rule: IntelligentSuggestionRule) => {
    setRuleSaving(true)
    try {
      const updatedRule = await updateIntelligentSuggestionRule(rule.id, { enabled: !rule.enabled })
      setRules((prev) => prev.map((current) => (current.id === rule.id ? updatedRule : current)))
      if (editingRuleId === rule.id && editingRuleDraft) {
        setEditingRuleDraft({ ...editingRuleDraft, enabled: updatedRule.enabled })
      }
      toast.success(`Rule ${updatedRule.enabled ? "enabled" : "disabled"}`)
    } catch (ruleError) {
      console.error("Failed to toggle intelligent suggestion rule:", ruleError)
      toast.error("Failed to update rule status")
    } finally {
      setRuleSaving(false)
    }
  }

  const startEditingRule = (rule: IntelligentSuggestionRule) => {
    const template = templateByKey.get(rule.template_key)
    const nextDraft = buildRuleDraft(template, rule.sort_order, {
      name: rule.name,
      stage_slug: rule.stage_key ?? rule.stage_slug ?? template?.default_stage_key ?? template?.default_stage_slug ?? "",
      business_days: rule.business_days,
      enabled: rule.enabled,
      sort_order: rule.sort_order,
    })
    if (!nextDraft) return
    setEditingRuleId(rule.id)
    setEditingRuleDraft(nextDraft)
  }

  const cancelEditingRule = () => {
    setEditingRuleId(null)
    setEditingRuleDraft(null)
  }

  const handleSaveEditingRule = async () => {
    if (!editingRuleId || !editingRuleDraft) return
    const template = templateByKey.get(editingRuleDraft.template_key)
    if (!template) {
      toast.error("Unknown template for rule")
      return
    }
    const stageSlug = requiresStageSelection(template)
      ? resolveStageSlug(template, editingRuleDraft.stage_slug)
      : null
    if (requiresStageSelection(template) && !stageSlug) {
      toast.error("Select a stage for this workflow rule")
      return
    }

    setRuleSaving(true)
    try {
      const selectedStage = stageSlug ? stageOptionByValue.get(stageSlug) : null
      const updatedRule = await updateIntelligentSuggestionRule(editingRuleId, {
        name: editingRuleDraft.name.trim() || template.name,
        stage_key: selectedStage?.stageKey ?? stageSlug,
        stage_slug: selectedStage?.slug ?? stageSlug,
        business_days: Math.max(1, Math.min(60, editingRuleDraft.business_days)),
        enabled: editingRuleDraft.enabled,
        sort_order: Math.max(0, editingRuleDraft.sort_order),
      })
      setRules((prev) =>
        prev
          .map((rule) => (rule.id === editingRuleId ? updatedRule : rule))
          .sort((left, right) => left.sort_order - right.sort_order),
      )
      cancelEditingRule()
      toast.success("Workflow rule updated")
    } catch (ruleError) {
      console.error("Failed to update intelligent suggestion rule:", ruleError)
      toast.error("Failed to update workflow rule")
    } finally {
      setRuleSaving(false)
    }
  }

  const handleDeleteRule = async (rule: IntelligentSuggestionRule) => {
    if (!confirm(`Delete rule "${rule.name}"?`)) return
    setRuleSaving(true)
    try {
      await deleteIntelligentSuggestionRule(rule.id)
      setRules((prev) => prev.filter((current) => current.id !== rule.id))
      if (editingRuleId === rule.id) cancelEditingRule()
      toast.success("Workflow rule deleted")
    } catch (ruleError) {
      console.error("Failed to delete intelligent suggestion rule:", ruleError)
      toast.error("Failed to delete workflow rule")
    } finally {
      setRuleSaving(false)
    }
  }

  const describeRule = (rule: IntelligentSuggestionRule) => {
    if (rule.rule_kind === "meeting_outcome_missing") {
      return `Passed scheduled meeting ${rule.business_days} business day${rule.business_days === 1 ? "" : "s"} but no outcome logged`
    }
    if (rule.template_key === "preapproval_stuck") {
      return `No updates in intake pre-approval stages for ${rule.business_days} business day${rule.business_days === 1 ? "" : "s"}`
    }
    return `${rule.stage_label ?? formatStageLabel(rule.stage_key ?? rule.stage_slug)} has no updates for ${rule.business_days} business day${rule.business_days === 1 ? "" : "s"}`
  }

  const getRuleStageLabel = (rule: IntelligentSuggestionRule) => {
    if (rule.rule_kind === "meeting_outcome_missing") {
      return "All Stages Applied"
    }
    if (rule.template_key === "preapproval_stuck") {
      return "Intake Pre-approval Stages"
    }
    return rule.stage_label ?? formatStageLabel(rule.stage_key ?? rule.stage_slug)
  }

  const buildStageInput = (
    id: string,
    value: string,
    onChange: (nextValue: string | null) => void,
    disabled = false,
  ) => {
    if (stageOptions.length > 0) {
      return (
        <Select value={value} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger id={id}>
            <SelectValue placeholder="Select stage">
              {(selected: string | null) => {
                if (!selected) return "Select stage"
                return stageLabelByRef.get(selected) ?? selected.replaceAll("_", " ")
              }}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {stageOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )
    }
    return (
      <Input
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Stage key (for example: new_unread)"
      />
    )
  }

  const newRuleTemplate = newRuleDraft ? templateByKey.get(newRuleDraft.template_key) : undefined
  const newRuleNeedsStage = requiresStageSelection(newRuleTemplate)
  const rulesPaused = !settings.enabled

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <div>
            <p className="font-medium">Enable Intelligent Suggestions</p>
            <p className="text-sm text-muted-foreground">
              Turn all intelligent suggestion workflows on or off for your organization.
            </p>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(checked) => setSettings((prev) => (prev ? { ...prev, enabled: checked } : prev))}
          />
        </div>
        {rulesPaused && (
          <p className="text-sm text-muted-foreground">
            Intelligent suggestions are paused globally. You can still configure rules below.
          </p>
        )}

        <div className="rounded-lg border border-border p-4 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-medium">Add Workflow Rule</p>
              <p className="text-sm text-muted-foreground">
                Build rules like "stuck on stage X for Y business days" or "follow up after Y days."
              </p>
            </div>
            <Button
              variant="outline"
              onClick={handleCreateRule}
              disabled={ruleSaving || !newRuleDraft || templates.length === 0}
            >
              <PlusIcon className="mr-2 size-4" aria-hidden="true" />
              Add Rule
            </Button>
          </div>

          {newRuleDraft ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="new-rule-template">Template</Label>
                <Select
                  value={newRuleDraft.template_key}
                  onValueChange={handleNewRuleTemplateChange}
                  disabled={ruleSaving || templates.length === 0}
                >
                  <SelectTrigger id="new-rule-template">
                    <SelectValue placeholder="Select template">
                      {(selected: string | null) => {
                        if (!selected) return "Select template"
                        return templateByKey.get(selected)?.name ?? selected.replaceAll("_", " ")
                      }}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((template) => (
                      <SelectItem key={template.template_key} value={template.template_key}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {newRuleTemplate && (
                  <p className="text-xs text-muted-foreground">{newRuleTemplate.description}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="new-rule-name">Rule name</Label>
                <Input
                  id="new-rule-name"
                  value={newRuleDraft.name}
                  disabled={ruleSaving}
                  onChange={(event) =>
                    setNewRuleDraft((prev) => (prev ? { ...prev, name: event.target.value } : prev))
                  }
                />
              </div>

              {newRuleNeedsStage && (
                <div className="space-y-2">
                  <Label htmlFor="new-rule-stage">Stage</Label>
                  {buildStageInput(
                    "new-rule-stage",
                    newRuleDraft.stage_slug,
                    (nextStage) =>
                      setNewRuleDraft((prev) =>
                        nextStage && prev ? { ...prev, stage_slug: nextStage } : prev,
                      ),
                    ruleSaving,
                  )}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="new-rule-days">Business days</Label>
                <Input
                  id="new-rule-days"
                  type="number"
                  min={1}
                  max={60}
                  disabled={ruleSaving}
                  value={newRuleDraft.business_days}
                  onChange={(event) => {
                    const parsed = Number.parseInt(event.target.value, 10)
                    const normalized = Number.isFinite(parsed) ? parsed : newRuleDraft.business_days
                    setNewRuleDraft((prev) =>
                      prev ? { ...prev, business_days: Math.max(1, Math.min(60, normalized)) } : prev,
                    )
                  }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No templates available. Reload to retry.</p>
          )}
        </div>

        <div className="space-y-3">
          <div>
            <p className="font-medium">Configured Workflow Rules</p>
            <p className="text-sm text-muted-foreground">
              Edit thresholds, target stages, priority, and enabled status.
            </p>
          </div>
          {rules.length === 0 && (
            <div className="rounded-lg border border-border p-4 text-sm text-muted-foreground">
              No intelligent suggestion rules configured.
            </div>
          )}
          {rules.map((rule) => {
            const template = templateByKey.get(rule.template_key)
            const isEditing = editingRuleId === rule.id && editingRuleDraft !== null
            const editingTemplate = isEditing ? templateByKey.get(editingRuleDraft.template_key) : undefined
            const editingNeedsStage = requiresStageSelection(editingTemplate)
            const ruleDescription = describeRule(rule)
            const ruleStageLabel = getRuleStageLabel(rule)

            return (
              <div key={rule.id} className="rounded-lg border border-border p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{rule.name}</p>
                    <p className="text-sm text-muted-foreground">{ruleDescription}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={rule.enabled ? "default" : "secondary"}>
                      {rule.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={ruleSaving}
                      onClick={() => handleToggleRuleEnabled(rule)}
                    >
                      {rule.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={ruleSaving}
                      onClick={() => startEditingRule(rule)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={ruleSaving}
                      onClick={() => handleDeleteRule(rule)}
                    >
                      <TrashIcon className="mr-1 size-4" aria-hidden="true" />
                      Delete
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 text-sm md:grid-cols-3">
                  <p><span className="font-medium">Template:</span> {template?.name ?? rule.template_key}</p>
                  <p><span className="font-medium">Stage:</span> {ruleStageLabel}</p>
                  <p><span className="font-medium">Priority:</span> {rule.sort_order}</p>
                </div>

                {isEditing && editingRuleDraft && (
                  <div className="rounded-md border border-border bg-muted/30 p-3 space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor={`edit-rule-name-${rule.id}`}>Rule name</Label>
                        <Input
                          id={`edit-rule-name-${rule.id}`}
                          value={editingRuleDraft.name}
                          disabled={ruleSaving}
                          onChange={(event) =>
                            setEditingRuleDraft((prev) =>
                              prev ? { ...prev, name: event.target.value } : prev,
                            )
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor={`edit-rule-days-${rule.id}`}>Business days</Label>
                        <Input
                          id={`edit-rule-days-${rule.id}`}
                          type="number"
                          min={1}
                          max={60}
                          disabled={ruleSaving}
                          value={editingRuleDraft.business_days}
                          onChange={(event) => {
                            const parsed = Number.parseInt(event.target.value, 10)
                            const normalized = Number.isFinite(parsed) ? parsed : editingRuleDraft.business_days
                            setEditingRuleDraft((prev) =>
                              prev
                                ? { ...prev, business_days: Math.max(1, Math.min(60, normalized)) }
                                : prev,
                            )
                          }}
                        />
                      </div>

                      {editingNeedsStage && (
                        <div className="space-y-2">
                          <Label htmlFor={`edit-rule-stage-${rule.id}`}>Stage</Label>
                          {buildStageInput(
                            `edit-rule-stage-${rule.id}`,
                            editingRuleDraft.stage_slug,
                            (nextStage) =>
                              setEditingRuleDraft((prev) =>
                                nextStage && prev ? { ...prev, stage_slug: nextStage } : prev,
                              ),
                            ruleSaving,
                          )}
                        </div>
                      )}

                      <div className="space-y-2">
                        <Label htmlFor={`edit-rule-priority-${rule.id}`}>Priority</Label>
                        <Input
                          id={`edit-rule-priority-${rule.id}`}
                          type="number"
                          min={0}
                          disabled={ruleSaving}
                          value={editingRuleDraft.sort_order}
                          onChange={(event) => {
                            const parsed = Number.parseInt(event.target.value, 10)
                            const normalized = Number.isFinite(parsed) ? parsed : editingRuleDraft.sort_order
                            setEditingRuleDraft((prev) =>
                              prev ? { ...prev, sort_order: Math.max(0, normalized) } : prev,
                            )
                          }}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor={`edit-rule-enabled-${rule.id}`}>Enabled</Label>
                        <div className="flex h-10 items-center rounded-md border border-input px-3">
                          <Switch
                            id={`edit-rule-enabled-${rule.id}`}
                            checked={editingRuleDraft.enabled}
                            disabled={ruleSaving}
                            onCheckedChange={(checked) =>
                              setEditingRuleDraft((prev) =>
                                prev ? { ...prev, enabled: checked } : prev,
                              )
                            }
                          />
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" disabled={ruleSaving} onClick={handleSaveEditingRule}>
                        Save Rule
                      </Button>
                      <Button size="sm" variant="outline" disabled={ruleSaving} onClick={cancelEditingRule}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="rounded-lg border border-border p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-medium">Daily digest notifications</p>
            <Switch
              disabled={!settings.enabled}
              checked={settings.daily_digest_enabled}
              onCheckedChange={(checked) =>
                setSettings((prev) => (prev ? { ...prev, daily_digest_enabled: checked } : prev))
              }
            />
          </div>
          <p className="text-sm text-muted-foreground">
            Send a daily digest to users when suggestions are available.
          </p>
          <div className="space-y-2 max-w-xs">
            <Label htmlFor="digest-hour">Digest hour (local org time, 0-23)</Label>
            <Input
              id="digest-hour"
              type="number"
              min={0}
              max={23}
              disabled={!settings.enabled || !settings.daily_digest_enabled}
              value={settings.digest_hour_local}
              onChange={(event) => setDigestField(event.target.value)}
            />
          </div>
        </div>
      </div>

      <Button onClick={handleSave} disabled={saving}>
        {saving ? (
          <>
            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            Saving…
          </>
        ) : saved ? (
          <>
            <CheckIcon className="mr-2 size-4" aria-hidden="true" />
            Saved!
          </>
        ) : (
          "Save Intelligent Suggestion Rules"
        )}
      </Button>
    </div>
  )
}

// =============================================================================
// Main Settings Page
// =============================================================================

function SettingsPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()

  const isAdmin = user?.role === "admin" || user?.role === "developer"

  type SettingsTab = "general" | "email-signature" | "intelligent-suggestions"
  const urlTabParam = searchParams.get("tab")
  const urlTab: SettingsTab = isAdmin
    && (urlTabParam === "email-signature" || urlTabParam === "intelligent-suggestions")
    ? urlTabParam
    : "general"
  const activeTab: SettingsTab = urlTab

  const handleTabChange = (value: string) => {
    const nextTab: SettingsTab = isAdmin
      && (value === "email-signature" || value === "intelligent-suggestions")
      ? value
      : "general"

    const nextParams = new URLSearchParams(searchParams.toString())
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

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <SettingsPageContent />
    </Suspense>
  )
}
