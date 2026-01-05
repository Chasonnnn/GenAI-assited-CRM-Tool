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
import { CameraIcon, MonitorIcon, SmartphoneIcon, LoaderIcon, CheckIcon, BellRingIcon, UploadIcon, TrashIcon, PaletteIcon } from "lucide-react"
import { useNotificationSettings, useUpdateNotificationSettings } from "@/lib/hooks/use-notifications"
import { useBrowserNotifications } from "@/lib/hooks/use-browser-notifications"
import { useAuth } from "@/lib/auth-context"
import { getOrgSettings, updateProfile, updateOrgSettings } from "@/lib/api/settings"
import { useOrgSignature, useUpdateOrgSignature, useUploadOrgLogo, useDeleteOrgLogo } from "@/lib/hooks/use-signature"

// Browser Notifications Card - handles permission request
function BrowserNotificationsCard() {
  const { isSupported, permission, requestPermission } = useBrowserNotifications()
  const [isRequesting, setIsRequesting] = useState(false)

  const handleRequestPermission = async () => {
    setIsRequesting(true)
    await requestPermission()
    setIsRequesting(false)
  }

  if (!isSupported) {
    return null // Don't show on unsupported browsers
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
              {permission === 'granted'
                ? 'Enabled - you will receive push notifications'
                : permission === 'denied'
                  ? 'Blocked - enable in browser settings'
                  : 'Enable to receive notifications when tab is not focused'}
            </p>
          </div>
          {permission === 'granted' ? (
            <Badge className="bg-green-500/10 text-green-600 border-green-500/20">Enabled</Badge>
          ) : permission === 'denied' ? (
            <Badge variant="secondary">Blocked</Badge>
          ) : (
            <Button onClick={handleRequestPermission} disabled={isRequesting} size="sm">
              {isRequesting ? (
                <><LoaderIcon className="mr-2 size-4 animate-spin" /> Requesting...</>
              ) : (
                'Enable'
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// Notification Settings Card - wired to real API
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
              <p className="text-sm text-muted-foreground">Get notified for new, confirmed, and cancelled appointments</p>
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


// Email Signature Branding Section - Admin only
function SignatureBrandingSection() {
  const { data: orgSig, isLoading } = useOrgSignature()
  const updateOrgSig = useUpdateOrgSignature()
  const uploadLogo = useUploadOrgLogo()
  const deleteLogo = useDeleteOrgLogo()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [template, setTemplate] = useState("")
  const [primaryColor, setPrimaryColor] = useState("#2563eb")
  const [companyName, setCompanyName] = useState("")
  const [address, setAddress] = useState("")
  const [phone, setPhone] = useState("")
  const [website, setWebsite] = useState("")
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (orgSig) {
      setTemplate(orgSig.signature_template || "classic")
      setPrimaryColor(orgSig.signature_primary_color || "#2563eb")
      setCompanyName(orgSig.signature_company_name || "")
      setAddress(orgSig.signature_address || "")
      setPhone(orgSig.signature_phone || "")
      setWebsite(orgSig.signature_website || "")
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
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
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
        <h3 className="font-medium">Email Signature Branding</h3>
        <p className="text-sm text-muted-foreground">
          Organization-wide email signature settings (Admin only)
        </p>
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
              accept="image/png,image/jpeg,image/gif"
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
            <p className="text-xs text-muted-foreground mt-1">
              Max 200x80px, PNG/JPG/GIF
            </p>
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
            placeholder="#2563eb"
          />
          <PaletteIcon className="size-4 text-muted-foreground" />
        </div>
      </div>

      {/* Company Info */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="sigCompanyName">Company Name</Label>
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
          <Label htmlFor="sigPhone">Phone</Label>
          <Input
            id="sigPhone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="(555) 123-4567"
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="sigAddress">Address</Label>
          <Textarea
            id="sigAddress"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="123 Main St, City, State 12345"
            rows={2}
          />
        </div>
      </div>

      <Button onClick={handleSave} disabled={updateOrgSig.isPending}>
        {updateOrgSig.isPending ? (
          <><LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...</>
        ) : saved ? (
          <><CheckIcon className="mr-2 size-4" /> Saved!</>
        ) : (
          "Save Signature Branding"
        )}
      </Button>
    </div>
  )
}


export default function SettingsPage() {
  const searchParams = useSearchParams()
  const { user, refetch } = useAuth()

  // Profile form state
  const [profileName, setProfileName] = useState(user?.display_name || "")
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileSaved, setProfileSaved] = useState(false)

  // Org form state
  const [orgName, setOrgName] = useState(user?.org_name || "")
  const [orgAddress, setOrgAddress] = useState("")
  const [orgPhone, setOrgPhone] = useState("")
  const [orgEmail, setOrgEmail] = useState("")
  const [orgSaving, setOrgSaving] = useState(false)
  const [orgSaved, setOrgSaved] = useState(false)

  const activeTab = (() => {
    const tab = searchParams?.get("tab")
    if (tab === "notifications") return tab
    return "general"
  })()

  const initials =
    user?.display_name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "??"

  useEffect(() => {
    if (!user) return
    if (!profileName) {
      setProfileName(user.display_name || "")
    }
    if (!orgName) {
      setOrgName(user.org_name || "")
    }
  }, [user, profileName, orgName])

  useEffect(() => {
    let isMounted = true
    const loadOrgSettings = async () => {
      try {
        const settings = await getOrgSettings()
        if (!isMounted) return
        setOrgName((prev) => prev || settings.name || "")
        setOrgAddress(settings.address || "")
        setOrgPhone(settings.phone || "")
        setOrgEmail(settings.email || "")
      } catch (error) {
        console.error("Failed to load organization settings:", error)
      }
    }
    if (user?.org_id) {
      loadOrgSettings()
    }
    return () => {
      isMounted = false
    }
  }, [user?.org_id])

  const handleSaveProfile = async () => {
    setProfileSaving(true)
    try {
      await updateProfile({
        display_name: profileName || undefined,
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
        {activeTab === "general" && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>General</CardTitle>
                <CardDescription>Profile, organization, and access settings</CardDescription>
              </CardHeader>
              <CardContent className="space-y-10">
                {/* Profile */}
                <div className="space-y-6">
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      <Avatar className="size-20">
                        <AvatarImage src="/avatars/user.jpg" />
                        <AvatarFallback>{initials}</AvatarFallback>
                      </Avatar>
                      <button
                        type="button"
                        className="absolute bottom-0 right-0 flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90"
                      >
                        <CameraIcon className="size-4" />
                      </button>
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
                        value={profileName}
                        onChange={(e) => setProfileName(e.target.value)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input id="email" type="email" defaultValue={user?.email || ""} disabled />
                      <p className="text-xs text-muted-foreground">Email is managed by SSO</p>
                    </div>

                    <div className="space-y-2">
                      <Label>Role</Label>
                      <div>
                        <Badge className="bg-primary/10 text-primary border-primary/20">
                          {user?.role || "unknown"}
                        </Badge>
                      </div>
                    </div>
                  </div>

                  <Button onClick={handleSaveProfile} disabled={profileSaving}>
                    {profileSaving ? (
                      <><LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...</>
                    ) : profileSaved ? (
                      <><CheckIcon className="mr-2 size-4" /> Saved!</>
                    ) : (
                      "Save Changes"
                    )}
                  </Button>
                </div>

                <div className="border-t border-border" />

                {/* Organization */}
                <div className="space-y-6">
                  <div>
                    <h3 className="font-medium">Organization</h3>
                    <p className="text-sm text-muted-foreground">Organization-wide defaults</p>
                  </div>

                  <div className="grid gap-6 md:grid-cols-2">
                    <div className="space-y-2 md:col-span-2">
                      <Label htmlFor="orgName">Organization Name</Label>
                      <Input
                        id="orgName"
                        value={orgName}
                        onChange={(e) => setOrgName(e.target.value)}
                      />
                    </div>

                    <div className="space-y-2 md:col-span-2">
                      <Label htmlFor="address">Address</Label>
                      <Textarea
                        id="address"
                        rows={3}
                        placeholder="-"
                        value={orgAddress}
                        onChange={(e) => setOrgAddress(e.target.value)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="orgPhone">Phone</Label>
                      <Input
                        id="orgPhone"
                        type="tel"
                        placeholder="-"
                        value={orgPhone}
                        onChange={(e) => setOrgPhone(e.target.value)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="orgEmail">Email</Label>
                      <Input
                        id="orgEmail"
                        type="email"
                        placeholder="-"
                        value={orgEmail}
                        onChange={(e) => setOrgEmail(e.target.value)}
                      />
                    </div>
                  </div>

                  <Button onClick={handleSaveOrg} disabled={orgSaving}>
                    {orgSaving ? (
                      <><LoaderIcon className="mr-2 size-4 animate-spin" /> Saving...</>
                    ) : orgSaved ? (
                      <><CheckIcon className="mr-2 size-4" /> Saved!</>
                    ) : (
                      "Save Changes"
                    )}
                  </Button>
                </div>

                <div className="border-t border-border" />

                {/* Email Signature Branding */}
                <SignatureBrandingSection />

                {/* Access */}
                <div className="space-y-6">
                  <div>
                    <h3 className="font-medium">Access</h3>
                    <p className="text-sm text-muted-foreground">2FA and session controls</p>
                  </div>

                  <div className="flex items-center justify-between rounded-lg border border-border p-4">
                    <div className="space-y-0.5">
                      <Label htmlFor="twoFactor">Two-factor authentication</Label>
                      <p className="text-sm text-muted-foreground">
                        Managed by Google Workspace + Duo
                      </p>
                    </div>
                    <Switch id="twoFactor" checked disabled />
                  </div>

                  <div className="space-y-3">
                    <h4 className="font-medium">Active Sessions</h4>
                    <div className="flex items-start justify-between rounded-lg border border-border p-4">
                      <div className="flex gap-3">
                        <MonitorIcon className="mt-0.5 size-5 text-muted-foreground" />
                        <div>
                          <p className="font-medium">Current session</p>
                          <p className="text-sm text-muted-foreground">This device</p>
                        </div>
                      </div>
                      <Badge className="bg-green-500/10 text-green-500 border-green-500/20">Current</Badge>
                    </div>

                    <div className="flex items-start justify-between rounded-lg border border-border p-4">
                      <div className="flex gap-3">
                        <SmartphoneIcon className="mt-0.5 size-5 text-muted-foreground" />
                        <div>
                          <p className="font-medium">Other session</p>
                          <p className="text-sm text-muted-foreground">—</p>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm" disabled>
                        Revoke
                      </Button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                      Account deletion is managed by your organization admin.
                    </p>
                    <p className="text-xs text-muted-foreground">v0.11.1</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === "notifications" && (
          <div className="space-y-6">
            <BrowserNotificationsCard />
            <NotificationsSettingsCard />
          </div>
        )}
      </div>
    </div>
  )
}
