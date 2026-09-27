"use client"

import { Suspense, use, useState, useRef } from "react"
import type { Route } from "next"
import NextImage from "next/image"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { ValidatedField } from "@/components/ui/field"
import { SaveBar } from "@/components/ui/save-bar"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PageHeader } from "@/components/page-header"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { focusFirstInvalid, useFormValidation } from "@/lib/forms/use-form-validation"
import { validateRequired } from "@/lib/forms/validators"
import { getSelectLabel, type SelectOption } from "@/lib/select-labels"
import DOMPurify from "dompurify"
import {
  CameraIcon,
  MonitorIcon,
  SmartphoneIcon,
  Loader2Icon,
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
import { updateProfile } from "@/lib/api/settings"
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
import { useOrgSettings, useUpdateOrgSettings } from "@/lib/hooks/use-settings"
import type { OrgSignature, SocialLink } from "@/lib/api/signature"
import type { OrgSettings } from "@/lib/api/settings"
import { toast } from "@/components/ui/toast"
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

type ProfileDraftState = {
  profileKey: string
  form: ProfileFormState
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

type OrgBrandingDraftState = {
  brandingKey: string
  form: OrgBrandingFormState
}

type OrgBrandingUiState = {
  saving: boolean
  previewLoading: boolean
  previewHtml: string | null
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

function createProfileDraftKey(
  userId: string,
  displayName: string,
  phone: string,
  title: string,
) {
  return [userId, displayName, phone, title].join("\u0000")
}

function createProfileDraftState(
  profileKey: string,
  displayName: string,
  phone: string,
  title: string,
): ProfileDraftState {
  return {
    profileKey,
    form: {
      name: displayName,
      phone,
      title,
    },
  }
}

function createOrgBrandingDraftKey(
  orgSig: OrgSignature | null | undefined,
  orgSettings: OrgSettings | null | undefined,
  orgName: string,
) {
  return [
    orgSig?.signature_template ?? "",
    orgSig?.signature_primary_color ?? "",
    orgSig?.signature_company_name ?? "",
    orgSig?.signature_address ?? "",
    orgSig?.signature_phone ?? "",
    orgSig?.signature_website ?? "",
    orgSig?.signature_disclaimer ?? "",
    orgSettings?.name ?? "",
    orgSettings?.address ?? "",
    orgSettings?.phone ?? "",
    orgSettings?.email ?? "",
    orgName,
  ].join("\u0000")
}

function createOrgBrandingDraftState(
  brandingKey: string,
  orgSig: OrgSignature | null | undefined,
  orgSettings: OrgSettings | null | undefined,
  orgName: string,
): OrgBrandingDraftState {
  return {
    brandingKey,
    form: {
      template: orgSig?.signature_template || "classic",
      primaryColor: orgSig?.signature_primary_color || "#E444A4",
      companyName: orgSig?.signature_company_name || orgSettings?.name || orgName,
      address: orgSig?.signature_address || orgSettings?.address || "",
      phone: orgSig?.signature_phone || orgSettings?.phone || "",
      website: orgSig?.signature_website || "",
      disclaimer: orgSig?.signature_disclaimer || "",
      orgEmail: orgSettings?.email || "",
    },
  }
}

function formatSessionDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function getSessionDeviceIcon(deviceInfo: string | null) {
  const info = deviceInfo?.toLowerCase() || ""
  if (info.includes("mobile") || info.includes("android") || info.includes("iphone")) {
    return <SmartphoneIcon className="mt-0.5 size-5 text-muted-foreground" aria-hidden="true" />
  }
  return <MonitorIcon className="mt-0.5 size-5 text-muted-foreground" aria-hidden="true" />
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
          <Button unstyled
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
          </Button>
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
  onDelete: () => Promise<unknown>
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
            <ConfirmDialog
              trigger={
                <Button unstyled
                  type="button"
                  disabled={deletePending}
                  className="absolute -right-2 -top-2 rounded-full bg-destructive p-1 text-destructive-foreground opacity-0 dark:bg-destructive/60 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                  aria-label="Remove organization logo"
                >
                  <TrashIcon className="size-3" aria-hidden="true" />
                </Button>
              }
              title="Remove the organization logo?"
              description="Email signatures show no logo until a new one is uploaded."
              confirmLabel="Remove logo"
              errorFallback="Couldn't remove the logo. Try again."
              onConfirm={onDelete}
            />
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
            aria-label="Organization logo upload"
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

// Matches the Input fill locally; changing components/ui/textarea.tsx would restyle every textarea.
const SIGNATURE_TEXTAREA_CLASS = "bg-transparent shadow-xs dark:bg-input/30"

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
              aria-label="Primary color"
              className="size-10 rounded cursor-pointer border"
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
            className={SIGNATURE_TEXTAREA_CLASS}
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
            className={SIGNATURE_TEXTAREA_CLASS}
          />
        </div>
      </div>
    </>
  )
}

function SignaturePreviewActions({
  previewLoading,
  previewHtml,
  onPreview,
}: {
  previewLoading: boolean
  previewHtml: string | null
  onPreview: () => Promise<void>
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

// Title is required: the API marks a profile without one incomplete (profile_complete in
// apps/api/app/routers/auth.py), and the app shell then sends the user back to /welcome.
function validateProfileForm(values: ProfileFormState) {
  return {
    name: validateRequired(values.name, "Enter your full name."),
    title: validateRequired(values.title, "Enter your title."),
  }
}

function ProfileSection() {
  const { user, refetch } = useAuth()
  const uploadAvatarMutation = useUploadAvatar()
  const deleteAvatarMutation = useDeleteAvatar()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const profileSectionRef = useRef<HTMLDivElement>(null)

  const [profileSaving, setProfileSaving] = useState(false)
  const userId = user?.user_id || ""
  const userDisplayName = user?.display_name || ""
  const userPhone = user?.phone || ""
  const userTitle = user?.title || ""
  const activeProfileKey = createProfileDraftKey(userId, userDisplayName, userPhone, userTitle)
  // useAuth().refetch is not awaitable. The saved values stand in as the baseline until the refreshed
  // user changes activeProfileKey, so the save bar does not reappear between save and refetch.
  const [savedProfile, setSavedProfile] = useState<{ profileKey: string; form: ProfileFormState } | null>(null)
  const profileBaseline = savedProfile?.profileKey === activeProfileKey
    ? savedProfile.form
    : { name: userDisplayName, phone: userPhone, title: userTitle }
  const [profileDraft, setProfileDraft] = useState<ProfileDraftState>(() =>
    createProfileDraftState(activeProfileKey, userDisplayName, userPhone, userTitle)
  )
  const profileForm = profileDraft.profileKey === activeProfileKey
    ? profileDraft.form
    : createProfileDraftState(activeProfileKey, userDisplayName, userPhone, userTitle).form

  const updateProfileForm = (field: keyof ProfileFormState, value: string) => {
    setProfileDraft((current) => {
      const activeDraft = current.profileKey === activeProfileKey
        ? current
        : createProfileDraftState(activeProfileKey, userDisplayName, userPhone, userTitle)

      return {
        profileKey: activeProfileKey,
        form: {
          ...activeDraft.form,
          [field]: value,
        },
      }
    })
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

  const profileValidation = useFormValidation({ values: profileForm, validate: validateProfileForm })

  const handleDeleteAvatar = async () => {
    await deleteAvatarMutation.mutateAsync()
    void refetch()
  }

  const profileChangeCount = (["name", "title", "phone"] as const).filter(
    (field) => profileForm[field] !== profileBaseline[field]
  ).length

  const handleDiscardProfile = () => {
    setProfileDraft({ profileKey: activeProfileKey, form: profileBaseline })
    profileValidation.reset()
  }

  const showProfileErrors = () => {
    focusFirstInvalid(profileSectionRef.current)
  }

  const handleSaveProfile = profileValidation.handleSubmit(async (values) => {
    setProfileSaving(true)
    try {
      const saved = {
        name: values.name.trim(),
        phone: values.phone.trim(),
        title: values.title.trim(),
      }
      // The API clears phone and title when it receives an empty string.
      await updateProfile({
        display_name: saved.name,
        phone: saved.phone,
        title: saved.title,
      })
      setSavedProfile({ profileKey: activeProfileKey, form: saved })
      setProfileDraft({ profileKey: activeProfileKey, form: saved })
      profileValidation.reset()
      toast.success("Profile saved")
      refetch()
    } catch (error) {
      const message = profileValidation.applyApiError(error, {
        fields: ["name", "phone", "title"],
        fallback: "Couldn't save your profile. Try again.",
      })
      if (message) toast.error(message)
    } finally {
      setProfileSaving(false)
    }
  })

  return (
    <div ref={profileSectionRef} className="space-y-6">
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
            aria-label="Profile photo upload"
            className="hidden"
          />
          <Button unstyled
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
          </Button>
          {user?.avatar_url && (
            <ConfirmDialog
              trigger={
                <Button unstyled
                  type="button"
                  disabled={deleteAvatarMutation.isPending}
                  className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground opacity-0 dark:bg-destructive/60 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                  aria-label="Remove profile photo"
                >
                  <TrashIcon className="size-3" aria-hidden="true" />
                </Button>
              }
              title="Remove your profile photo?"
              confirmLabel="Remove photo"
              errorFallback="Couldn't remove your profile photo. Try again."
              onConfirm={handleDeleteAvatar}
            />
          )}
        </div>
        <div>
          <h3 className="font-medium">Profile</h3>
          <p className="text-sm text-muted-foreground">Managed via Google SSO</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <ValidatedField label="Full Name" id="fullName" error={profileValidation.errorFor("name")}>
          {(control) => (
            <Input
              {...control}
              name="fullName"
              autoComplete="name"
              value={profileForm.name}
              onChange={(e) => {
                updateProfileForm("name", e.target.value)
                // Show the error while typing so the field agrees with the save bar's error count.
                profileValidation.touch("name")
              }}
              onBlur={() => profileValidation.touch("name")}
            />
          )}
        </ValidatedField>

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

        <ValidatedField
          label="Title"
          id="title"
          error={profileValidation.errorFor("title")}
          description="Displayed in email signatures"
        >
          {(control) => (
            <Input
              {...control}
              name="title"
              autoComplete="organization-title"
              value={profileForm.title}
              onChange={(e) => {
                updateProfileForm("title", e.target.value)
                profileValidation.touch("title")
              }}
              onBlur={() => profileValidation.touch("title")}
            />
          )}
        </ValidatedField>

        {/* Same field layout as Title so the two columns stay aligned. */}
        <ValidatedField label="Phone" id="phone" description="Displayed in email signatures">
          {(control) => (
            <Input
              {...control}
              name="phone"
              autoComplete="tel"
              type="tel"
              value={profileForm.phone}
              onChange={(e) => updateProfileForm("phone", e.target.value)}
              placeholder="(555) 123-4567"
            />
          )}
        </ValidatedField>

        <div className="space-y-2">
          <Label>Role</Label>
          <div>
            <Badge className="bg-primary/10 text-primary border-primary/20">
              {ROLE_LABELS[user?.role ?? ""] || "Unknown"}
            </Badge>
          </div>
        </div>
      </div>

      <SaveBar
        className="-mx-6"
        dirty={profileChangeCount > 0}
        changeCount={profileChangeCount}
        errorCount={
          profileValidation.isValid
            ? 0
            : Math.max(1, Object.values(validateProfileForm(profileForm)).filter(Boolean).length)
        }
        onErrorsClick={showProfileErrors}
        saving={profileSaving}
        onSave={() => void handleSaveProfile()}
        onDiscard={handleDiscardProfile}
      />
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
  const [pendingRevokeId, setPendingRevokeId] = useState<string | null>(null)
  const [revokeOpen, setRevokeOpen] = useState(false)
  const pendingRevokeSession = sessions?.find((session) => session.id === pendingRevokeId)

  const handleConfirmRevokeSession = async () => {
    if (!pendingRevokeId) return
    await revokeSession.mutateAsync(pendingRevokeId)
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
          <ConfirmDialog
            trigger={
              <Button variant="destructive-ghost" size="sm" disabled={revokeAllSessions.isPending}>
                Log out all others
              </Button>
            }
            title="Log out all other devices?"
            description={`${otherSessions.length} ${otherSessions.length === 1 ? "session is" : "sessions are"} signed out. This device stays signed in.`}
            confirmLabel="Log out others"
            errorFallback="Couldn't log out the other devices. Try again."
            onConfirm={() => revokeAllSessions.mutateAsync()}
          />
        )}
      </div>

      {sessions?.map((session) => (
        <div
          key={session.id}
          className="flex items-start justify-between rounded-lg border border-border p-4"
        >
          <div className="flex gap-3">
            {getSessionDeviceIcon(session.device_info)}
            <div>
              <p className="font-medium">
                {session.device_info || "Unknown device"}
                {session.is_current && (
                  <span className="ml-2 text-xs text-muted-foreground">(this device)</span>
                )}
              </p>
              <p className="text-sm text-muted-foreground">
                {session.ip_address || "Unknown IP"} &middot; Last active{" "}
                {formatSessionDate(session.last_active_at)}
              </p>
            </div>
          </div>
          {session.is_current ? (
            <Badge className="bg-green-500/10 text-green-500 border-green-500/20">Current</Badge>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setPendingRevokeId(session.id)
                setRevokeOpen(true)
              }}
              aria-label={`Revoke session on ${session.device_info || "unknown device"}`}
            >
              Revoke
            </Button>
          )}
        </div>
      ))}

      {(!sessions || sessions.length === 0) && (
        <div className="rounded-lg border border-border p-4 text-center text-muted-foreground">
          No active sessions found
        </div>
      )}

      <ConfirmDialog
        open={revokeOpen}
        onOpenChange={setRevokeOpen}
        title={`Revoke the session on ${pendingRevokeSession?.device_info || "this device"}?`}
        description="The device is signed out."
        confirmLabel="Revoke session"
        errorFallback="Couldn't revoke this session. Try again."
        onConfirm={handleConfirmRevokeSession}
      />
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

// Each value is its display text. The API labels older lowercase keys at render time;
// keep in sync with SOCIAL_PLATFORM_LABELS in apps/api/app/services/signature_template_service.py.
const SOCIAL_PLATFORMS = ["LinkedIn", "Instagram", "Facebook", "X", "TikTok", "Website"] as const
const SOCIAL_PLATFORM_ALIASES: Record<string, string> = { twitter: "X" }
const MAX_SOCIAL_LINKS = 6

type SocialLinkDraft = SocialLink & { id: string }
type SocialLinkErrors = { platform?: string | undefined; url?: string | undefined }

/** Maps older free-text values such as "linkedin" onto the known platform spelling. */
function normalizeSocialPlatform(platform: string): string {
  const trimmed = platform.trim()
  const key = trimmed.toLowerCase()
  return SOCIAL_PLATFORMS.find((option) => option.toLowerCase() === key) ?? SOCIAL_PLATFORM_ALIASES[key] ?? trimmed
}

/** Known platforms plus the row's current value when it is an older custom one, so it still shows. */
function getSocialPlatformOptions(current: string): SelectOption[] {
  const options: SelectOption[] = SOCIAL_PLATFORMS.map((platform) => ({ value: platform, label: platform }))
  if (current && !options.some((option) => option.value === current)) {
    options.push({ value: current, label: current })
  }
  return options
}

function getSocialPlatformLabel(value: string | null | undefined): string {
  return getSelectLabel(value, getSocialPlatformOptions(value ?? ""), { emptyLabel: "Select platform" })
}

function createSavedSocialLinks(links: SocialLink[] | null | undefined): SocialLinkDraft[] {
  return (links ?? []).map((link, index) => ({
    id: `saved-${index}`,
    platform: normalizeSocialPlatform(link.platform),
    url: link.url,
  }))
}

function getSocialLinkErrors(link: SocialLink): SocialLinkErrors {
  const platform = link.platform.trim()
  const url = link.url.trim()
  if (!platform && !url) return {}
  return {
    platform: platform ? undefined : "Select a platform.",
    url: !url ? "Enter a URL." : url.startsWith("https://") ? undefined : "Enter a URL that starts with https://.",
  }
}

function countSocialLinkChanges(saved: SocialLink[], draft: SocialLink[]): number {
  let changes = 0
  for (let index = 0; index < Math.max(saved.length, draft.length); index += 1) {
    const before = saved[index]
    const after = draft[index]
    if (before?.platform !== after?.platform || before?.url !== after?.url) changes += 1
  }
  return changes
}

function SocialLinksFields({
  links,
  errors,
  onChange,
  onUrlBlur,
  onAdd,
  onRemove,
}: {
  links: SocialLinkDraft[]
  /** Errors to show, keyed by row id. */
  errors: Record<string, SocialLinkErrors>
  onChange: (id: string, field: keyof SocialLink, value: string) => void
  onUrlBlur: (id: string) => void
  onAdd: () => void
  onRemove: (id: string) => void
}) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium flex items-center gap-2">
          <LinkIcon className="size-4" aria-hidden="true" />
          Social Links
        </h3>
      </div>

      <div className="space-y-3">
        {links.map((link, i) => {
          const rowErrors = errors[link.id] ?? {}
          const platformErrorId = rowErrors.platform ? `social-platform-${link.id}-error` : undefined
          const urlErrorId = rowErrors.url ? `social-url-${link.id}-error` : undefined
          return (
            <div key={link.id} className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-3 sm:flex-nowrap">
                <Select
                  value={link.platform}
                  onValueChange={(value) => onChange(link.id, "platform", value ?? "")}
                >
                  <SelectTrigger
                    className="w-40"
                    aria-label={`Social platform ${i + 1}`}
                    aria-invalid={rowErrors.platform ? true : undefined}
                    aria-describedby={platformErrorId}
                  >
                    <SelectValue placeholder="Select platform">{getSocialPlatformLabel}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {getSocialPlatformOptions(link.platform).map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  value={link.url}
                  onChange={(e) => onChange(link.id, "url", e.target.value)}
                  onBlur={() => onUrlBlur(link.id)}
                  placeholder="https://…"
                  className="min-w-0 flex-1"
                  name={`social-url-${i}`}
                  autoComplete="url"
                  aria-label={`Social URL ${i + 1}`}
                  aria-invalid={rowErrors.url ? true : undefined}
                  aria-describedby={urlErrorId}
                />
                <Button
                  type="button"
                  variant="destructive-ghost"
                  size="icon"
                  onClick={() => onRemove(link.id)}
                  className="text-muted-foreground"
                  aria-label={`Remove social link ${i + 1}`}
                >
                  <TrashIcon className="size-4" aria-hidden="true" />
                </Button>
              </div>
              {rowErrors.platform ? (
                <p id={platformErrorId} className="text-sm text-destructive">{rowErrors.platform}</p>
              ) : null}
              {rowErrors.url ? (
                <p id={urlErrorId} className="text-sm text-destructive">{rowErrors.url}</p>
              ) : null}
            </div>
          )
        })}

        {links.length < MAX_SOCIAL_LINKS && (
          <Button type="button" variant="outline" size="sm" onClick={onAdd}>
            <PlusIcon className="mr-2 size-4" aria-hidden="true" />
            Add Social Link
          </Button>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Organization Branding Section
// =============================================================================

/** Email Signature tab: branding fields and social links share one draft and one save bar. */
function EmailSignatureSettings() {
  const { user, refetch } = useAuth()
  const { data: orgSig, isLoading: sigLoading } = useOrgSignature()
  const updateOrgSig = useUpdateOrgSignature()
  const uploadLogo = useUploadOrgLogo()
  const deleteLogo = useDeleteOrgLogo()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const orgSettingsQuery = useOrgSettings({ enabled: Boolean(user?.org_id) })
  const updateOrgSettingsMutation = useUpdateOrgSettings()
  const orgSettings = orgSettingsQuery.data
  const orgName = user?.org_name || ""
  const activeBrandingKey = createOrgBrandingDraftKey(orgSig, orgSettings, orgName)
  const [brandingDraft, setBrandingDraft] = useState<OrgBrandingDraftState>(() =>
    createOrgBrandingDraftState(activeBrandingKey, orgSig, orgSettings, orgName)
  )
  const savedBrandingForm = createOrgBrandingDraftState(activeBrandingKey, orgSig, orgSettings, orgName).form
  const brandingForm = brandingDraft.brandingKey === activeBrandingKey
    ? brandingDraft.form
    : savedBrandingForm
  const [brandingUi, setBrandingUi] = useState<OrgBrandingUiState>({
    saving: false,
    previewLoading: false,
    previewHtml: null,
  })

  // Social links follow the same pattern: the draft resets when the saved links change.
  const savedSocialLinks = orgSig?.signature_social_links ?? null
  const activeLinksKey = JSON.stringify(savedSocialLinks ?? [])
  const savedLinks = createSavedSocialLinks(savedSocialLinks)
  const [linksDraft, setLinksDraft] = useState<{ linksKey: string; links: SocialLinkDraft[] }>(() => ({
    linksKey: activeLinksKey,
    links: savedLinks,
  }))
  const links = linksDraft.linksKey === activeLinksKey ? linksDraft.links : savedLinks
  const nextLinkIdRef = useRef(0)
  const [revealedLinkIds, setRevealedLinkIds] = useState<ReadonlySet<string>>(() => new Set())
  const [showAllLinkErrors, setShowAllLinkErrors] = useState(false)
  const editorRef = useRef<HTMLDivElement>(null)

  const linkErrors: Record<string, SocialLinkErrors> = {}
  let linkErrorCount = 0
  for (const link of links) {
    const rowErrors = getSocialLinkErrors(link)
    const rowErrorCount = Number(Boolean(rowErrors.platform)) + Number(Boolean(rowErrors.url))
    linkErrorCount += rowErrorCount
    if (rowErrorCount > 0 && (showAllLinkErrors || revealedLinkIds.has(link.id))) {
      linkErrors[link.id] = rowErrors
    }
  }

  const brandingChangeCount = (Object.keys(savedBrandingForm) as (keyof OrgBrandingFormState)[]).filter(
    (field) => brandingForm[field] !== savedBrandingForm[field]
  ).length
  const changeCount = brandingChangeCount + countSocialLinkChanges(savedLinks, links)

  const updateLinks = (update: (current: SocialLinkDraft[]) => SocialLinkDraft[]) => {
    setLinksDraft((current) => ({
      linksKey: activeLinksKey,
      links: update(current.linksKey === activeLinksKey ? current.links : savedLinks),
    }))
  }

  const addLink = () => {
    nextLinkIdRef.current += 1
    const id = `new-${nextLinkIdRef.current}`
    updateLinks((current) =>
      current.length >= MAX_SOCIAL_LINKS ? current : [...current, { id, platform: "", url: "" }]
    )
  }

  const removeLink = (id: string) => {
    updateLinks((current) => current.filter((link) => link.id !== id))
  }

  const changeLink = (id: string, field: keyof SocialLink, value: string) => {
    updateLinks((current) => current.map((link) => (link.id === id ? { ...link, [field]: value } : link)))
  }

  const revealLinkErrors = (id: string) => {
    setRevealedLinkIds((current) => (current.has(id) ? current : new Set(current).add(id)))
  }

  const showLinkErrors = () => {
    setShowAllLinkErrors(true)
    window.requestAnimationFrame(() => focusFirstInvalid(editorRef.current))
  }

  const handleDiscard = () => {
    setBrandingDraft(createOrgBrandingDraftState(activeBrandingKey, orgSig, orgSettings, orgName))
    setLinksDraft({ linksKey: activeLinksKey, links: savedLinks })
    setRevealedLinkIds(new Set())
    setShowAllLinkErrors(false)
  }
  const orgSettingsLoading = Boolean(user?.org_id) && orgSettingsQuery.isLoading
  const orgSettingsError = orgSettingsQuery.isError
    ? "Unable to load organization settings. Please retry."
    : null

  const sanitizedPreviewHtml = brandingUi.previewHtml ? DOMPurify.sanitize(brandingUi.previewHtml) : null

  const updateBrandingForm = <K extends keyof OrgBrandingFormState>(field: K, value: OrgBrandingFormState[K]) => {
    setBrandingDraft((current) => {
      const activeDraft = current.brandingKey === activeBrandingKey
        ? current
        : createOrgBrandingDraftState(activeBrandingKey, orgSig, orgSettings, orgName)

      return {
        brandingKey: activeBrandingKey,
        form: {
          ...activeDraft.form,
          [field]: value,
        },
      }
    })
  }

  const handleSave = async () => {
    if (linkErrorCount > 0) {
      showLinkErrors()
      return
    }
    setBrandingUi((current) => ({ ...current, saving: true }))
    try {
      const validLinks = links
        .map((link) => ({ platform: link.platform.trim(), url: link.url.trim() }))
        .filter((link) => link.platform && link.url)
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
        signature_social_links: validLinks.length > 0 ? validLinks : null,
      }

      if (orgSettingsError) {
        await updateOrgSig.mutateAsync(signaturePayload)
      } else {
        await Promise.all([
          updateOrgSig.mutateAsync(signaturePayload),
          updateOrgSettingsMutation.mutateAsync({
            ...(trimmedCompanyName ? { name: trimmedCompanyName } : {}),
            ...(trimmedAddress ? { address: trimmedAddress } : {}),
            ...(trimmedPhone ? { phone: trimmedPhone } : {}),
            ...(trimmedEmail ? { email: trimmedEmail } : {}),
          }),
        ])
        refetch()
      }

      setRevealedLinkIds(new Set())
      setShowAllLinkErrors(false)
      toast.success("Email signature saved")
    } catch (error) {
      const message = getActionErrorMessage(error, "Couldn't save the email signature. Try again.")
      if (message) toast.error(message)
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

  const handleDeleteLogo = () => deleteLogo.mutateAsync()

  const handlePreviewTemplate = async () => {
    setBrandingUi((current) => ({ ...current, previewLoading: true }))
    try {
      const result = await getOrgSignaturePreview(brandingForm.template)
      setBrandingUi((current) => ({ ...current, previewHtml: result.html }))
    } catch {
      // Silent fail
    }
    setBrandingUi((current) => ({ ...current, previewLoading: false }))
  }

  if (sigLoading || orgSettingsLoading) {
    return (
      <Card>
        <CardContent>
          <div className="animate-pulse motion-reduce:animate-none flex gap-4" role="status" aria-label="Loading">
            <div className="h-24 w-full bg-muted rounded" />
          </div>
        </CardContent>
      </Card>
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
    <>
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MailIcon className="size-5" aria-hidden="true" />
          Organization Email Signature
        </CardTitle>
      </CardHeader>
      <CardContent ref={editorRef} className="space-y-10">
    <div className="space-y-6">
      <div>
        <h3 className="font-medium flex items-center gap-2">
          <PaletteIcon className="size-4" aria-hidden="true" />
          Organization Branding
        </h3>
      </div>

      {orgSettingsError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{orgSettingsError}</span>
            <Button
              variant="outline"
              onClick={() => {
                void orgSettingsQuery.refetch()
              }}
            >
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
        orgSettingsError={orgSettingsError}
        onFieldChange={updateBrandingForm}
      />

      <SignaturePreviewActions
        previewLoading={brandingUi.previewLoading}
        previewHtml={sanitizedPreviewHtml}
        onPreview={handlePreviewTemplate}
      />
    </div>

    <div className="border-t border-border" />

    <SocialLinksFields
      links={links}
      errors={linkErrors}
      onChange={changeLink}
      onUrlBlur={revealLinkErrors}
      onAdd={addLink}
      onRemove={removeLink}
    />
      </CardContent>
    </Card>

    <SaveBar
      className="-mx-6"
      dirty={changeCount > 0}
      changeCount={changeCount}
      errorCount={linkErrorCount}
      onErrorsClick={showLinkErrors}
      saving={brandingUi.saving}
      onSave={() => void handleSave()}
      onDiscard={handleDiscard}
    />
    </>
  )
}

// =============================================================================
// Main Settings Page
// =============================================================================

function SettingsPageContent({ searchParams }: { searchParams: SettingsPageSearchParams }) {
  const { replace } = useRouter()
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
    replace(nextUrl as Route, { scroll: false })
  }

  return (
    <div className="flex min-h-screen flex-col">
      <PageHeader title="Settings" />

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
                </CardHeader>
                <CardContent className="space-y-10">
                  {/* Profile Section */}
                  <ProfileSection />

                  <div className="border-t border-border" />

                  {/* Access Section */}
                  <div className="space-y-6">
                    <div>
                      <h3 className="font-medium">Access</h3>
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
              <EmailSignatureSettings />
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
