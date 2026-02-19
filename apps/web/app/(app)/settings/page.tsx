"use client"

import { useEffect, useState, useRef, useCallback, useMemo } from "react"
import { useRouter, useSearchParams } from "next/navigation"
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

const ROLE_LABELS: Record<string, string> = {
  intake_specialist: "Intake Specialist",
  case_manager: "Case Manager",
  admin: "Admin",
  developer: "Developer",
}

// =============================================================================
// Profile Section with Avatar Upload, Phone, Title
// =============================================================================

function ProfileSection() {
  const { user, refetch } = useAuth()
  const uploadAvatarMutation = useUploadAvatar()
  const deleteAvatarMutation = useDeleteAvatar()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [profileName, setProfileName] = useState(user?.display_name || "")
  const [profilePhone, setProfilePhone] = useState(user?.phone || "")
  const [profileTitle, setProfileTitle] = useState(user?.title || "")
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileSaved, setProfileSaved] = useState(false)

  useEffect(() => {
    if (user) {
      setProfileName(user.display_name || "")
      setProfilePhone(user.phone || "")
      setProfileTitle(user.title || "")
    }
  }, [user])

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
      const trimmedName = profileName.trim()
      const trimmedPhone = profilePhone.trim()
      const trimmedTitle = profileTitle.trim()
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
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
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
            value={profileTitle}
            onChange={(e) => setProfileTitle(e.target.value)}
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
            value={profilePhone}
            onChange={(e) => setProfilePhone(e.target.value)}
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
        {links.map((link, i) => (
          <div key={i} className="flex items-center gap-3">
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
        ))}

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

  const [template, setTemplate] = useState("")
  const [primaryColor, setPrimaryColor] = useState("#E444A4")
  const [companyName, setCompanyName] = useState("")
  const [address, setAddress] = useState("")
  const [phone, setPhone] = useState("")
  const [website, setWebsite] = useState("")
  const [disclaimer, setDisclaimer] = useState("")
  const [orgEmail, setOrgEmail] = useState("")
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [orgSettingsLoading, setOrgSettingsLoading] = useState(true)
  const [orgSettingsError, setOrgSettingsError] = useState<string | null>(null)
  const [orgDefaults, setOrgDefaults] = useState({ name: "", address: "", phone: "" })
  const [initialized, setInitialized] = useState(false)

  const sanitizedPreviewHtml = useMemo(
    () => (previewHtml ? DOMPurify.sanitize(previewHtml) : null),
    [previewHtml]
  )

  const isMountedRef = useRef(true)

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const loadOrgSettings = useCallback(async () => {
    if (!user?.org_id) return
    setOrgSettingsLoading(true)
    setOrgSettingsError(null)
    try {
      const settings = await getOrgSettings()
      if (!isMountedRef.current) return
      setOrgDefaults({
        name: settings.name || "",
        address: settings.address || "",
        phone: settings.phone || "",
      })
      setOrgEmail(settings.email || "")
    } catch (error) {
      console.error("Failed to load organization settings:", error)
      if (!isMountedRef.current) return
      setOrgSettingsError("Unable to load organization settings. Please retry.")
    } finally {
      if (isMountedRef.current) setOrgSettingsLoading(false)
    }
  }, [user?.org_id])

  useEffect(() => {
    if (user?.org_id) {
      loadOrgSettings()
    } else {
      setOrgSettingsLoading(false)
    }
  }, [user?.org_id, loadOrgSettings])

  useEffect(() => {
    if (initialized) return
    if (sigLoading || orgSettingsLoading) return
    setTemplate(orgSig?.signature_template || "classic")
    setPrimaryColor(orgSig?.signature_primary_color || "#E444A4")
    setCompanyName(orgSig?.signature_company_name || orgDefaults.name || user?.org_name || "")
    setAddress(orgSig?.signature_address || orgDefaults.address || "")
    setPhone(orgSig?.signature_phone || orgDefaults.phone || "")
    setWebsite(orgSig?.signature_website || "")
    setDisclaimer(orgSig?.signature_disclaimer || "")
    setInitialized(true)
  }, [initialized, sigLoading, orgSettingsLoading, orgSig, orgDefaults, user?.org_name])

  const handleSave = async () => {
    setSaving(true)
    try {
      const trimmedCompanyName = companyName.trim()
      const trimmedAddress = address.trim()
      const trimmedPhone = phone.trim()
      const trimmedWebsite = website.trim()
      const trimmedDisclaimer = disclaimer.trim()
      const trimmedEmail = orgEmail.trim()

      const signaturePayload = {
        signature_template: template,
        signature_primary_color: primaryColor,
        signature_company_name: trimmedCompanyName || null,
        signature_address: trimmedAddress || null,
        signature_phone: trimmedPhone || null,
        signature_website: trimmedWebsite || null,
        signature_disclaimer: trimmedDisclaimer || null,
      }

      if (orgSettingsError) {
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

      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (error) {
      console.error("Failed to save organization branding:", error)
      toast.error("Failed to save organization branding")
    } finally {
      setSaving(false)
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

  if (sigLoading || orgSettingsLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse motion-reduce:animate-none flex gap-4">
          <div className="h-24 w-full bg-muted rounded" />
        </div>
      </div>
    )
  }

  const templates = orgSig?.available_templates || [
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

      {orgSettingsError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{orgSettingsError}</span>
            <Button variant="outline" onClick={loadOrgSettings}>
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Template Selection */}
      <div className="space-y-3">
        <Label>Signature Template</Label>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3" role="radiogroup" aria-label="Signature template">
          {templates.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTemplate(t.id)}
              aria-pressed={template === t.id}
              aria-label={`Template ${t.name}`}
              className={`p-3 rounded-lg border text-left transition-colors ${template === t.id
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground"
                }`}
            >
              <div className="font-medium text-sm">{t.name}</div>
              <div className="text-xs text-muted-foreground">{t.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Logo Upload */}
      <div className="space-y-3">
        <Label>Organization Logo</Label>
        <div className="flex items-center gap-4">
          {orgSig?.signature_logo_url ? (
            <div className="relative group">
              <img
                src={orgSig.signature_logo_url}
                alt="Organization Logo"
                width={200}
                height={80}
                className="h-16 w-auto border rounded"
              />
              <button
                type="button"
                onClick={handleDeleteLogo}
                disabled={deleteLogo.isPending}
                className="absolute -top-2 -right-2 p-1 bg-destructive text-destructive-foreground rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label="Remove organization logo"
              >
                <TrashIcon className="size-3" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <div className="h-16 w-32 border-2 border-dashed rounded flex items-center justify-center text-muted-foreground">
              No logo
            </div>
          )}
          <div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleLogoUpload}
              accept="image/png,image/jpeg"
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadLogo.isPending}
            >
              {uploadLogo.isPending ? (
                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : (
                <UploadIcon className="mr-2 size-4" aria-hidden="true" />
              )}
              Upload Logo
            </Button>
            <p className="text-xs text-muted-foreground mt-1">Max 200x80px, PNG/JPG</p>
          </div>
        </div>
      </div>

      {/* Primary Color */}
      <div className="space-y-2">
        <Label htmlFor="primaryColor">Primary Color</Label>
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="color"
              id="primaryColor"
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
              className="w-10 h-10 rounded cursor-pointer border"
            />
          </div>
          <Input
            value={primaryColor}
            onChange={(e) => setPrimaryColor(e.target.value)}
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
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Your Organization"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigWebsite">Website</Label>
          <Input
            id="sigWebsite"
            name="sigWebsite"
            autoComplete="url"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="https://www.example.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigPhone">Phone</Label>
          <Input
            id="sigPhone"
            name="sigPhone"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
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
            value={orgEmail}
            onChange={(e) => setOrgEmail(e.target.value)}
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
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="123 Main St, City, State 12345"
            rows={2}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="sigDisclaimer">Disclaimer / Legal Footer</Label>
          <Textarea
            id="sigDisclaimer"
            name="sigDisclaimer"
            value={disclaimer}
            onChange={(e) => setDisclaimer(e.target.value)}
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
            onClick={async () => {
              setPreviewLoading(true)
              try {
                const result = await getOrgSignaturePreview(template)
                setPreviewHtml(result.html)
              } catch {
                // Silent fail
              } finally {
                setPreviewLoading(false)
              }
            }}
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
          <Button onClick={handleSave} disabled={saving || sigLoading || orgSettingsLoading}>
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

        {sanitizedPreviewHtml && (
          <div className="rounded-lg border border-border p-6 bg-white">
            <p className="text-xs text-muted-foreground mb-3 pb-3 border-b">
              Preview with sample employee data:
            </p>
            <div
              className="prose prose-sm prose-stone max-w-none text-stone-900"
              dangerouslySetInnerHTML={{ __html: sanitizedPreviewHtml }}
            />
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Main Settings Page
// =============================================================================

export default function SettingsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()

  const isAdmin = user?.role === "admin" || user?.role === "developer"

  type SettingsTab = "general" | "email-signature"
  const urlTabParam = searchParams.get("tab")
  const urlTab: SettingsTab =
    isAdmin && urlTabParam === "email-signature" ? "email-signature" : "general"
  const activeTab: SettingsTab = urlTab

  const handleTabChange = (value: string) => {
    const nextTab: SettingsTab =
      isAdmin && value === "email-signature" ? "email-signature" : "general"

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
        </Tabs>
      </div>
    </div>
  )
}
