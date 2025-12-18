"use client"

import { useEffect, useState } from "react"
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
import { CameraIcon, CheckIcon, MonitorIcon, SmartphoneIcon, LoaderIcon, History, GitBranch, FileText } from "lucide-react"
import { useNotificationSettings, useUpdateNotificationSettings } from "@/lib/hooks/use-notifications"
import { usePipelines, usePipelineVersions, useRollbackPipeline } from "@/lib/hooks/use-pipelines"
import { useEmailTemplates, useTemplateVersions, useRollbackTemplate } from "@/lib/hooks/use-email-templates"
import { VersionHistoryModal, type VersionItem } from "@/components/version-history-modal"
import { useAuth } from "@/lib/auth-context"
import { Mail } from "lucide-react"
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
              <Label htmlFor="case_status_changed">Case status changes</Label>
              <p className="text-sm text-muted-foreground">Get notified when case status changes</p>
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
        </div>
      </CardContent>
    </Card>
  )
}

// Pipelines Settings Card - with version history
function PipelinesSettingsCard() {
  const { user } = useAuth()
  const { data: pipelines, isLoading } = usePipelines()
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)

  const { data: versions, isLoading: versionsLoading } = usePipelineVersions(selectedPipelineId)
  const rollbackMutation = useRollbackPipeline()

  const selectedPipeline = pipelines?.find(p => p.id === selectedPipelineId)
  const isDeveloper = user?.role === 'developer'

  const handleOpenHistory = (pipelineId: string) => {
    setSelectedPipelineId(pipelineId)
    setHistoryOpen(true)
  }

  const handleRollback = (version: number) => {
    if (!selectedPipelineId) return
    rollbackMutation.mutate(
      { id: selectedPipelineId, version },
      {
        onSuccess: () => {
          setHistoryOpen(false)
        },
      }
    )
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
    <>
      <Card>
        <CardHeader>
          <CardTitle>Case Pipelines</CardTitle>
          <CardDescription>Manage your organization&apos;s case status pipelines</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {pipelines?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No pipelines configured
            </div>
          ) : (
            pipelines?.map((pipeline) => (
              <div
                key={pipeline.id}
                className="flex items-center justify-between rounded-lg border border-border p-4"
              >
                <div className="flex items-center gap-4">
                  <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
                    <GitBranch className="size-5 text-primary" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{pipeline.name}</h3>
                      {pipeline.is_default && (
                        <Badge variant="secondary" className="text-xs">Default</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {pipeline.stages.length} stages · v{pipeline.current_version}
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleOpenHistory(pipeline.id)}
                >
                  <History className="h-4 w-4 mr-1" />
                  History
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {selectedPipeline && (
        <VersionHistoryModal
          open={historyOpen}
          onOpenChange={setHistoryOpen}
          title={selectedPipeline.name}
          entityType="pipeline"
          versions={(versions || []).map(v => ({
            id: v.id,
            version: v.version,
            payload: v.payload as Record<string, unknown>,
            comment: v.comment,
            created_by_user_id: v.created_by_user_id,
            created_at: v.created_at,
          }))}
          currentVersion={selectedPipeline.current_version}
          isLoading={versionsLoading}
          onRollback={handleRollback}
          isRollingBack={rollbackMutation.isPending}
          canRollback={isDeveloper}
        />
      )}
    </>
  )
}

// Email Templates Settings Card - with version history
function EmailTemplatesSettingsCard() {
  const { user } = useAuth()
  const { data: templates, isLoading } = useEmailTemplates(false) // include inactive
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)

  const { data: versions, isLoading: versionsLoading } = useTemplateVersions(selectedTemplateId)
  const rollbackMutation = useRollbackTemplate()

  const selectedTemplate = templates?.find(t => t.id === selectedTemplateId)
  const isDeveloper = user?.role === 'developer'

  const handleOpenHistory = (templateId: string) => {
    setSelectedTemplateId(templateId)
    setHistoryOpen(true)
  }

  const handleRollback = (version: number) => {
    if (!selectedTemplateId) return
    rollbackMutation.mutate(
      { id: selectedTemplateId, version },
      {
        onSuccess: () => {
          setHistoryOpen(false)
        },
      }
    )
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
    <>
      <Card>
        <CardHeader>
          <CardTitle>Email Templates</CardTitle>
          <CardDescription>Manage your organization&apos;s email templates with version history</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {templates?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No email templates configured
            </div>
          ) : (
            templates?.map((template) => (
              <div
                key={template.id}
                className="flex items-center justify-between rounded-lg border border-border p-4"
              >
                <div className="flex items-center gap-4">
                  <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
                    <Mail className="size-5 text-primary" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{template.name}</h3>
                      {!template.is_active && (
                        <Badge variant="secondary" className="text-xs">Inactive</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {template.subject}
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleOpenHistory(template.id)}
                >
                  <History className="h-4 w-4 mr-1" />
                  History
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {selectedTemplate && (
        <VersionHistoryModal
          open={historyOpen}
          onOpenChange={setHistoryOpen}
          title={selectedTemplate.name}
          entityType="email_template"
          versions={(versions || []).map(v => ({
            id: v.id,
            version: v.version,
            payload: v.payload as Record<string, unknown>,
            comment: v.comment,
            created_by_user_id: v.created_by_user_id,
            created_at: v.created_at,
          }))}
          currentVersion={1} // selectedTemplate doesn't have current_version in list type
          isLoading={versionsLoading}
          onRollback={handleRollback}
          isRollingBack={rollbackMutation.isPending}
          canRollback={isDeveloper}
        />
      )}
    </>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const canManageQueues = user?.role && ['manager', 'developer'].includes(user.role)

  const validTabs = new Set([
    "profile",
    "organization",
    "notifications",
    "integrations",
    "security",
    "pipelines",
    "email-templates",
  ])

  const normalizeTab = (tab: string | null) => (tab && validTabs.has(tab) ? tab : "profile")

  const tabParam = searchParams.get("tab")
  const [activeTab, setActiveTab] = useState(() => normalizeTab(tabParam))

  useEffect(() => {
    setActiveTab((current) => {
      const normalized = normalizeTab(tabParam)
      return current === normalized ? current : normalized
    })
  }, [tabParam])

  const handleTabChange = (value: string) => {
    if (!validTabs.has(value)) return

    setActiveTab(value)

    const nextParams = new URLSearchParams(searchParams.toString())
    if (value === "profile") {
      nextParams.delete("tab")
    } else {
      nextParams.set("tab", value)
    }

    const query = nextParams.toString()
    router.replace(query ? `/settings?${query}` : "/settings")
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
        <Tabs value={activeTab} onValueChange={handleTabChange} className="flex flex-col gap-6 lg:flex-row">
          {/* Left Sidebar - Tabs Menu */}
          <Card className="h-fit lg:w-64">
            <CardContent className="p-2">
              <TabsList className="flex w-full flex-col items-stretch gap-1 bg-transparent">
                <TabsTrigger
                  value="profile"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  Profile
                </TabsTrigger>
                <TabsTrigger
                  value="organization"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  Organization
                </TabsTrigger>
                <TabsTrigger
                  value="notifications"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  Notifications
                </TabsTrigger>
                <TabsTrigger
                  value="integrations"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  Integrations
                </TabsTrigger>
                <TabsTrigger
                  value="security"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  Security
                </TabsTrigger>
                <TabsTrigger
                  value="pipelines"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  <GitBranch className="mr-2 h-4 w-4" />
                  Pipelines
                </TabsTrigger>
                <TabsTrigger
                  value="email-templates"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  <Mail className="mr-2 h-4 w-4" />
                  Email Templates
                </TabsTrigger>
                {canManageQueues && (
                  <a href="/settings/queues" className="w-full">
                    <TabsTrigger
                      value="queues"
                      className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary w-full"
                    >
                      Queue Management
                    </TabsTrigger>
                  </a>
                )}
                <a href="/settings/audit" className="w-full">
                  <TabsTrigger
                    value="audit"
                    className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary w-full"
                  >
                    <FileText className="mr-2 h-4 w-4" />
                    Audit Log
                  </TabsTrigger>
                </a>
              </TabsList>
            </CardContent>
          </Card>

          {/* Right Content Area */}
          <div className="flex-1">
            {/* Profile Tab */}
            <TabsContent value="profile" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>Profile Settings</CardTitle>
                  <CardDescription>Manage your personal information and preferences</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Avatar Upload */}
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      <Avatar className="size-20">
                        <AvatarImage src="/avatars/user.jpg" />
                        <AvatarFallback>JD</AvatarFallback>
                      </Avatar>
                      <button className="absolute bottom-0 right-0 flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90">
                        <CameraIcon className="size-4" />
                      </button>
                    </div>
                    <div>
                      <h3 className="font-medium">Profile Picture</h3>
                      <p className="text-sm text-muted-foreground">Upload a new avatar</p>
                    </div>
                  </div>

                  {/* Full Name */}
                  <div className="space-y-2">
                    <Label htmlFor="fullName">Full Name</Label>
                    <Input id="fullName" defaultValue="John Doe" />
                  </div>

                  {/* Email (disabled) */}
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" defaultValue="john.doe@example.com" disabled />
                    <p className="text-xs text-muted-foreground">Email cannot be changed</p>
                  </div>

                  {/* Phone */}
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input id="phone" type="tel" defaultValue="+1 (555) 123-4567" />
                  </div>

                  {/* Role */}
                  <div className="space-y-2">
                    <Label>Role</Label>
                    <div>
                      <Badge className="bg-primary/10 text-primary border-primary/20">Admin</Badge>
                    </div>
                  </div>

                  <Button>Save Changes</Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Organization Tab */}
            <TabsContent value="organization" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>Organization Settings</CardTitle>
                  <CardDescription>Manage your organization details</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Organization Name */}
                  <div className="space-y-2">
                    <Label htmlFor="orgName">Organization Name</Label>
                    <Input id="orgName" defaultValue="Surrogacy Solutions Inc." />
                  </div>

                  {/* Address */}
                  <div className="space-y-2">
                    <Label htmlFor="address">Address</Label>
                    <Textarea
                      id="address"
                      rows={3}
                      defaultValue="123 Main Street&#10;Suite 100&#10;San Francisco, CA 94105"
                    />
                  </div>

                  {/* Phone */}
                  <div className="space-y-2">
                    <Label htmlFor="orgPhone">Phone</Label>
                    <Input id="orgPhone" type="tel" defaultValue="+1 (555) 987-6543" />
                  </div>

                  {/* Email */}
                  <div className="space-y-2">
                    <Label htmlFor="orgEmail">Email</Label>
                    <Input id="orgEmail" type="email" defaultValue="info@surrogacysolutions.com" />
                  </div>

                  {/* Logo Upload */}
                  <div className="space-y-2">
                    <Label>Organization Logo</Label>
                    <div className="flex items-center gap-4">
                      <div className="flex size-16 items-center justify-center rounded-lg border border-border bg-muted">
                        <span className="text-xs text-muted-foreground">Logo</span>
                      </div>
                      <Button variant="outline">Upload Logo</Button>
                    </div>
                  </div>

                  <Button>Save Changes</Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Notifications Tab */}
            <TabsContent value="notifications" className="mt-0">
              <NotificationsSettingsCard />
            </TabsContent>

            {/* Integrations Tab */}
            <TabsContent value="integrations" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>Integrations</CardTitle>
                  <CardDescription>Manage your third-party integrations</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between rounded-lg border border-border p-4">
                    <div className="flex items-center gap-4">
                      <div className="flex size-12 items-center justify-center rounded-lg bg-blue-500/10">
                        <span className="text-2xl">📘</span>
                      </div>
                      <div>
                        <h3 className="font-medium">Meta Leads</h3>
                        <div className="flex items-center gap-2">
                          <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
                            <CheckIcon className="mr-1 size-3" />
                            Connected
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <Button variant="outline">Disconnect</Button>
                  </div>

                  <div className="flex items-center justify-between rounded-lg border border-border p-4">
                    <div className="flex items-center gap-4">
                      <div className="flex size-12 items-center justify-center rounded-lg bg-red-500/10">
                        <span className="text-2xl">📅</span>
                      </div>
                      <div>
                        <h3 className="font-medium">Google Calendar</h3>
                        <Badge variant="secondary" className="text-muted-foreground">
                          Not connected
                        </Badge>
                      </div>
                    </div>
                    <Button>Connect</Button>
                  </div>

                  <div className="flex items-center justify-between rounded-lg border border-border p-4">
                    <div className="flex items-center gap-4">
                      <div className="flex size-12 items-center justify-center rounded-lg bg-purple-500/10">
                        <span className="text-2xl">💬</span>
                      </div>
                      <div>
                        <h3 className="font-medium">Slack</h3>
                        <Badge variant="secondary" className="text-muted-foreground">
                          Not connected
                        </Badge>
                      </div>
                    </div>
                    <Button>Connect</Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Security Tab */}
            <TabsContent value="security" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>Security Settings</CardTitle>
                  <CardDescription>Manage your account security and active sessions</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-4">
                    <h3 className="font-medium">Change Password</h3>
                    <div className="space-y-2">
                      <Label htmlFor="currentPassword">Current Password</Label>
                      <Input id="currentPassword" type="password" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="newPassword">New Password</Label>
                      <Input id="newPassword" type="password" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirmPassword">Confirm New Password</Label>
                      <Input id="confirmPassword" type="password" />
                    </div>
                    <Button>Update Password</Button>
                  </div>

                  <div className="border-t border-border pt-6">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="twoFactor">Two-factor authentication</Label>
                        <p className="text-sm text-muted-foreground">Add an extra layer of security</p>
                      </div>
                      <Switch id="twoFactor" />
                    </div>
                  </div>

                  <div className="border-t border-border pt-6">
                    <h3 className="mb-4 font-medium">Active Sessions</h3>
                    <div className="space-y-3">
                      <div className="flex items-start justify-between rounded-lg border border-border p-4">
                        <div className="flex gap-3">
                          <MonitorIcon className="mt-0.5 size-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">Chrome on MacBook Pro</p>
                            <p className="text-sm text-muted-foreground">San Francisco, CA • Last active now</p>
                          </div>
                        </div>
                        <Badge className="bg-green-500/10 text-green-500 border-green-500/20">Current</Badge>
                      </div>

                      <div className="flex items-start justify-between rounded-lg border border-border p-4">
                        <div className="flex gap-3">
                          <SmartphoneIcon className="mt-0.5 size-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">Safari on iPhone 14</p>
                            <p className="text-sm text-muted-foreground">
                              San Francisco, CA • Last active 2 hours ago
                            </p>
                          </div>
                        </div>
                        <Button variant="ghost" size="sm">
                          Revoke
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-border pt-6">
                    <div className="space-y-4">
                      <div>
                        <h3 className="font-medium text-destructive">Delete Account</h3>
                        <p className="text-sm text-muted-foreground">
                          Permanently delete your account and all associated data
                        </p>
                      </div>
                      <Button variant="destructive">Delete Account</Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Pipelines Tab */}
            <TabsContent value="pipelines" className="mt-0">
              <PipelinesSettingsCard />
            </TabsContent>

            {/* Email Templates Tab */}
            <TabsContent value="email-templates" className="mt-0">
              <EmailTemplatesSettingsCard />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  )
}
