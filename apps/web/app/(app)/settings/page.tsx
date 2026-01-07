"use client"

import { useEffect, useState, useRef } from "react"
import { useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  CameraIcon,
  MonitorIcon,
  SmartphoneIcon,
  LoaderIcon,
  CheckIcon,
  BellRingIcon,
  UploadIcon,
  TrashIcon,
  PaletteIcon,
  PlusIcon,
  MailIcon,
  EyeIcon,
  GlobeIcon,
  LinkIcon,
} from "lucide-react"
import { useNotificationSettings, useUpdateNotificationSettings } from "@/lib/hooks/use-notifications"
import { useBrowserNotifications } from "@/lib/hooks/use-browser-notifications"
import { useAuth } from "@/lib/auth-context"
import { getOrgSettings, updateProfile, updateOrgSettings } from "@/lib/api/settings"
import {
  useOrgSignature,
  useUpdateOrgSignature,
  useUploadOrgLogo,
  useDeleteOrgLogo,
  useOrgSignaturePreview,
} from "@/lib/hooks/use-signature"
import {
  useSessions,
  useRevokeSession,
  useRevokeAllSessions,
  useUploadAvatar,
  useDeleteAvatar,
} from "@/lib/hooks/use-sessions"
import type { SocialLink } from "@/lib/api/signature"

// =============================================================================
// Browser Notifications Card
// =============================================================================

function BrowserNotificationsCard() {
  const { isSupported, permission, requestPermission } = useBrowserNotifications()
  const [isRequesting, setIsRequesting] = useState(false)

  const handleRequestPermission = async () => {
    setIsRequesting(true)
    await requestPermission()
    setIsRequesting(false)
  }

  if (!isSupported) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BellRingIcon className="size-5" />
          Browser Notifications
        </CardTitle>
        <CardDescription>Get desktop notifications when new updates arrive</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Desktop push notifications</Label>
            <p className="text-sm text-muted-foreground">
              {permission === "granted"
                ? "Enabled - you will receive push notifications"
                : permission === "denied"
                  ? "Blocked - enable in browser settings"
                  : "Enable to receive notifications when tab is not focused"}
            </p>
          </div>
          {permission === "granted" ? (
            <Badge className="bg-green-500/10 text-green-600 border-green-500/20">Enabled</Badge>
          ) : permission === "denied" ? (
            <Badge variant="secondary">Blocked</Badge>
          ) : (
            <Button onClick={handleRequestPermission} disabled={isRequesting} size="sm">
              {isRequesting ? (
                <>
                  <LoaderIcon className="mr-2 size-4 animate-spin" /> Requesting...
                </>
              ) : (
                "Enable"
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// Notification Settings Card
// =============================================================================

function NotificationsSettingsCard() {
  const { data: settings, isLoading } = useNotificationSettings()
  const updateMutation = useUpdateNotificationSettings()

  const handleToggle = (key: string, value: boolean) => {
    updateMutation.mutate({ [key]: value })
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-12 flex items-center justify-center">
          <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>In-App Notification Preferences</CardTitle>
        <CardDescription>Control which notifications you receive</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="case_assigned">Case assigned to me</Label>
              <p className="text-sm text-muted-foreground">Get notified when a case is assigned to you</p>
            </div>
            <Switch
              id="case_assigned"
              checked={settings?.case_assigned ?? true}
              onCheckedChange={(checked) => handleToggle("case_assigned", checked)}
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="case_status_changed">Case stage changes</Label>
              <p className="text-sm text-muted-foreground">Get notified when case stage changes</p>
            </div>
            <Switch
              id="case_status_changed"
              checked={settings?.case_status_changed ?? true}
              onCheckedChange={(checked) => handleToggle("case_status_changed", checked)}
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="case_handoff">Case handoff events</Label>
              <p className="text-sm text-muted-foreground">Get notified for handoff requests and approvals</p>
            </div>
            <Switch
              id="case_handoff"
              checked={settings?.case_handoff ?? true}
              onCheckedChange={(checked) => handleToggle("case_handoff", checked)}
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="task_assigned">Task assigned to me</Label>
              <p className="text-sm text-muted-foreground">Get notified when a task is assigned to you</p>
            </div>
            <Switch
              id="task_assigned"
              checked={settings?.task_assigned ?? true}
              onCheckedChange={(checked) => handleToggle("task_assigned", checked)}
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="workflow_approvals">Workflow approvals</Label>
              <p className="text-sm text-muted-foreground">Get notified when a workflow needs your decision</p>
            </div>
            <Switch
              id="workflow_approvals"
              checked={settings?.workflow_approvals ?? true}
              onCheckedChange={(checked) => handleToggle("workflow_approvals", checked)}
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="task_reminders">Task due date reminders</Label>
              <p className="text-sm text-muted-foreground">Get notified when tasks are due soon or overdue</p>
            </div>
            <Switch
              id="task_reminders"
              checked={settings?.task_reminders ?? true}
              onCheckedChange={(checked) => handleToggle("task_reminders", checked)}
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="appointments">Appointment updates</Label>
              <p className="text-sm text-muted-foreground">
                Get notified for new, confirmed, and cancelled appointments
              </p>
            </div>
            <Switch
              id="appointments"
              checked={settings?.appointments ?? true}
              onCheckedChange={(checked) => handleToggle("appointments", checked)}
              disabled={updateMutation.isPending}
            />
          </div>
        </div>
      </CardContent>
    </Card>
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
      alert("Please select a PNG, JPEG, or WebP image")
      return
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert("Image must be less than 2MB")
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
      await updateProfile({
        display_name: profileName || undefined,
        phone: profilePhone || undefined,
        title: profileTitle || undefined,
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
          >
            {uploadAvatarMutation.isPending ? (
              <LoaderIcon className="size-3.5 animate-spin" />
            ) : (
              <CameraIcon className="size-3.5" />
            )}
          </button>
          {user?.avatar_url && (
            <button
              type="button"
              onClick={handleDeleteAvatar}
              disabled={deleteAvatarMutation.isPending}
              className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <TrashIcon className="size-3" />
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
          <Input id="fullName" value={profileName} onChange={(e) => setProfileName(e.target.value)} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" defaultValue={user?.email || ""} disabled />
          <p className="text-xs text-muted-foreground">Email is managed by SSO</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
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
            <Badge className="bg-primary/10 text-primary border-primary/20">{user?.role || "unknown"}</Badge>
          </div>
        </div>
      </div>

      <Button onClick={handleSaveProfile} disabled={profileSaving}>
        {profileSaving ? (
          <>
            <LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...
          </>
        ) : profileSaved ? (
          <>
            <CheckIcon className="mr-2 size-4" /> Saved!
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
      return <SmartphoneIcon className="mt-0.5 size-5 text-muted-foreground" />
    }
    return <MonitorIcon className="mt-0.5 size-5 text-muted-foreground" />
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <h4 className="font-medium">Active Sessions</h4>
        <div className="flex items-center justify-center py-8">
          <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
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
              <LoaderIcon className="mr-2 size-4 animate-spin" />
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
                <LoaderIcon className="size-4 animate-spin" />
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
// Organization Section (Moved to Email Signature tab)
// =============================================================================

function OrganizationSection() {
  const { user, refetch } = useAuth()

  const [orgName, setOrgName] = useState(user?.org_name || "")
  const [orgAddress, setOrgAddress] = useState("")
  const [orgPhone, setOrgPhone] = useState("")
  const [orgEmail, setOrgEmail] = useState("")
  const [orgSaving, setOrgSaving] = useState(false)
  const [orgSaved, setOrgSaved] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let isMounted = true
    const loadOrgSettings = async () => {
      try {
        const settings = await getOrgSettings()
        if (!isMounted) return
        setOrgName(settings.name || "")
        setOrgAddress(settings.address || "")
        setOrgPhone(settings.phone || "")
        setOrgEmail(settings.email || "")
      } catch (error) {
        console.error("Failed to load organization settings:", error)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    if (user?.org_id) {
      loadOrgSettings()
    }
    return () => {
      isMounted = false
    }
  }, [user?.org_id])

  const handleSaveOrg = async () => {
    setOrgSaving(true)
    try {
      await updateOrgSettings({
        name: orgName || undefined,
        address: orgAddress || undefined,
        phone: orgPhone || undefined,
        email: orgEmail || undefined,
      })
      setOrgSaved(true)
      setTimeout(() => setOrgSaved(false), 2000)
      refetch()
    } catch (error) {
      console.error("Failed to save organization:", error)
    } finally {
      setOrgSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse flex gap-4">
          <div className="h-24 w-full bg-muted rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium">Organization Info</h3>
        <p className="text-sm text-muted-foreground">
          Company details shown in email signatures
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="orgName">Organization Name</Label>
          <Input id="orgName" value={orgName} onChange={(e) => setOrgName(e.target.value)} />
        </div>

        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="address">Address</Label>
          <Textarea
            id="address"
            rows={3}
            placeholder="123 Main St, City, State 12345"
            value={orgAddress}
            onChange={(e) => setOrgAddress(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="orgPhone">Phone</Label>
          <Input
            id="orgPhone"
            type="tel"
            placeholder="(555) 123-4567"
            value={orgPhone}
            onChange={(e) => setOrgPhone(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="orgEmail">Email</Label>
          <Input
            id="orgEmail"
            type="email"
            placeholder="contact@company.com"
            value={orgEmail}
            onChange={(e) => setOrgEmail(e.target.value)}
          />
        </div>
      </div>

      <Button onClick={handleSaveOrg} disabled={orgSaving}>
        {orgSaving ? (
          <>
            <LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...
          </>
        ) : orgSaved ? (
          <>
            <CheckIcon className="mr-2 size-4" /> Saved!
          </>
        ) : (
          "Save Changes"
        )}
      </Button>
    </div>
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
      alert("Maximum 6 social links allowed")
      return
    }
    setLinks([...links, { platform: "", url: "" }])
  }

  const removeLink = (index: number) => {
    setLinks(links.filter((_, i) => i !== index))
  }

  const updateLink = (index: number, field: keyof SocialLink, value: string) => {
    const newLinks = [...links]
    newLinks[index] = { ...newLinks[index], [field]: value }
    setLinks(newLinks)
  }

  const handleSave = async () => {
    // Filter out empty links
    const validLinks = links.filter((l) => l.platform.trim() && l.url.trim())

    // Validate URLs
    for (const link of validLinks) {
      if (!link.url.startsWith("https://")) {
        alert(`URL must start with https:// (${link.platform})`)
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
        <div className="animate-pulse flex gap-4">
          <div className="h-24 w-full bg-muted rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium flex items-center gap-2">
          <LinkIcon className="size-4" />
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
            />
            <Input
              value={link.url}
              onChange={(e) => updateLink(i, "url", e.target.value)}
              placeholder="https://..."
              className="flex-1"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => removeLink(i)}
              className="text-destructive hover:text-destructive"
            >
              <TrashIcon className="size-4" />
            </Button>
          </div>
        ))}

        {links.length < 6 && (
          <Button type="button" variant="outline" size="sm" onClick={addLink}>
            <PlusIcon className="mr-2 size-4" />
            Add Social Link
          </Button>
        )}
      </div>

      <Button onClick={handleSave} disabled={updateOrgSig.isPending}>
        {updateOrgSig.isPending ? (
          <>
            <LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...
          </>
        ) : saved ? (
          <>
            <CheckIcon className="mr-2 size-4" /> Saved!
          </>
        ) : (
          "Save Social Links"
        )}
      </Button>
    </div>
  )
}

// =============================================================================
// Signature Branding Section
// =============================================================================

function SignatureBrandingSection() {
  const { data: orgSig, isLoading } = useOrgSignature()
  const updateOrgSig = useUpdateOrgSignature()
  const uploadLogo = useUploadOrgLogo()
  const deleteLogo = useDeleteOrgLogo()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [template, setTemplate] = useState("")
  const [primaryColor, setPrimaryColor] = useState("#14b8a6")
  const [companyName, setCompanyName] = useState("")
  const [address, setAddress] = useState("")
  const [phone, setPhone] = useState("")
  const [website, setWebsite] = useState("")
  const [disclaimer, setDisclaimer] = useState("")
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (orgSig) {
      setTemplate(orgSig.signature_template || "classic")
      setPrimaryColor(orgSig.signature_primary_color || "#14b8a6")
      setCompanyName(orgSig.signature_company_name || "")
      setAddress(orgSig.signature_address || "")
      setPhone(orgSig.signature_phone || "")
      setWebsite(orgSig.signature_website || "")
      setDisclaimer(orgSig.signature_disclaimer || "")
    }
  }, [orgSig])

  const handleSave = async () => {
    await updateOrgSig.mutateAsync({
      signature_template: template,
      signature_primary_color: primaryColor,
      signature_company_name: companyName || null,
      signature_address: address || null,
      signature_phone: phone || null,
      signature_website: website || null,
      signature_disclaimer: disclaimer || null,
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const allowedTypes = ["image/png", "image/jpeg"]
      if (!allowedTypes.includes(file.type)) {
        alert("Logo must be a PNG or JPEG file")
        return
      }
      if (file.size > 1024 * 1024) {
        alert("Logo must be less than 1MB")
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

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse flex gap-4">
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
          <PaletteIcon className="size-4" />
          Signature Branding
        </h3>
        <p className="text-sm text-muted-foreground">Template and visual style for email signatures</p>
      </div>

      {/* Template Selection */}
      <div className="space-y-3">
        <Label>Signature Template</Label>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {templates.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTemplate(t.id)}
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
                className="h-16 w-auto border rounded"
              />
              <button
                type="button"
                onClick={handleDeleteLogo}
                disabled={deleteLogo.isPending}
                className="absolute -top-2 -right-2 p-1 bg-destructive text-destructive-foreground rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <TrashIcon className="size-3" />
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
                <LoaderIcon className="mr-2 size-4 animate-spin" />
              ) : (
                <UploadIcon className="mr-2 size-4" />
              )}
              Upload Logo
            </Button>
            <p className="text-xs text-muted-foreground mt-1">Max 200x80px, PNG/JPG</p>
          </div>
        </div>
      </div>

      {/* Primary Color */}
      <div className="space-y-2">
        <Label>Primary Color</Label>
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="color"
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
              className="w-10 h-10 rounded cursor-pointer border"
            />
          </div>
          <Input
            value={primaryColor}
            onChange={(e) => setPrimaryColor(e.target.value)}
            className="w-28 font-mono text-sm"
            placeholder="#14b8a6"
          />
        </div>
      </div>

      {/* Company Info for Signature */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="sigCompanyName">Company Name (in signature)</Label>
          <Input
            id="sigCompanyName"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Your Company"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigWebsite">Website</Label>
          <Input
            id="sigWebsite"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="https://www.example.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sigPhone">Phone (in signature)</Label>
          <Input
            id="sigPhone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="(555) 123-4567"
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="sigAddress">Address (in signature)</Label>
          <Textarea
            id="sigAddress"
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

      <Button onClick={handleSave} disabled={updateOrgSig.isPending}>
        {updateOrgSig.isPending ? (
          <>
            <LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...
          </>
        ) : saved ? (
          <>
            <CheckIcon className="mr-2 size-4" /> Saved!
          </>
        ) : (
          "Save Signature Branding"
        )}
      </Button>
    </div>
  )
}

// =============================================================================
// Signature Preview Section
// =============================================================================

function SignaturePreviewSection() {
  const { refetch: refetchPreview } = useOrgSignaturePreview()
  const [preview, setPreview] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handlePreview = async () => {
    setIsLoading(true)
    try {
      const result = await refetchPreview()
      if (result.data?.html) {
        setPreview(result.data.html)
      }
    } catch (error) {
      console.error("Failed to load preview:", error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium flex items-center gap-2">
          <EyeIcon className="size-4" />
          Signature Preview
        </h3>
        <p className="text-sm text-muted-foreground">
          Preview how email signatures look with sample data
        </p>
      </div>

      <Button variant="outline" onClick={handlePreview} disabled={isLoading}>
        {isLoading ? (
          <>
            <LoaderIcon className="mr-2 size-4 animate-spin" /> Loading...
          </>
        ) : (
          <>
            <EyeIcon className="mr-2 size-4" /> Preview Signature
          </>
        )}
      </Button>

      {preview && (
        <div className="rounded-lg border border-border p-6 bg-white">
          <p className="text-xs text-muted-foreground mb-3 pb-3 border-b">
            Preview with sample employee data:
          </p>
          <div dangerouslySetInnerHTML={{ __html: preview }} />
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Settings Page
// =============================================================================

export default function SettingsPage() {
  const searchParams = useSearchParams()
  const { user } = useAuth()

  const isAdmin = user?.role === "admin" || user?.role === "developer"

  const activeTab = (() => {
    const tab = searchParams?.get("tab")
    if (tab === "email-signature" && isAdmin) return tab
    return "general"
  })()

  const handleTabChange = (value: string) => {
    const url = new URL(window.location.href)
    if (value === "general") {
      url.searchParams.delete("tab")
    } else {
      url.searchParams.set("tab", value)
    }
    window.history.pushState({}, "", url.toString())
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
                <MailIcon className="size-4" />
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
                      <p className="text-xs text-muted-foreground">v0.16.00</p>
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
                      <MailIcon className="size-5" />
                      Email Signature Settings
                    </CardTitle>
                    <CardDescription>
                      Organization-wide email signature configuration. These settings apply to all users.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-10">
                    {/* Organization Info */}
                    <OrganizationSection />

                    <div className="border-t border-border" />

                    {/* Social Links */}
                    <SocialLinksSection />

                    <div className="border-t border-border" />

                    {/* Signature Branding */}
                    <SignatureBrandingSection />

                    <div className="border-t border-border" />

                    {/* Signature Preview */}
                    <SignaturePreviewSection />
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
