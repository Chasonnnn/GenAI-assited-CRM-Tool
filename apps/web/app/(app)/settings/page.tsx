"use client"

import { useState } from "react"
import { useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { CameraIcon, MonitorIcon, SmartphoneIcon, LoaderIcon, History, GitBranch } from "lucide-react"
import { useNotificationSettings, useUpdateNotificationSettings } from "@/lib/hooks/use-notifications"
import { usePipelines, usePipelineVersions, useRollbackPipeline } from "@/lib/hooks/use-pipelines"
import { VersionHistoryModal } from "@/components/version-history-modal"
import { useAuth } from "@/lib/auth-context"
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

export default function SettingsPage() {
  const searchParams = useSearchParams()

  const { user } = useAuth()
  const activeTab = (() => {
    const tab = searchParams?.get("tab")
    if (tab === "notifications" || tab === "pipelines") return tab
    return "general"
  })()

  const initials =
    user?.display_name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "??"

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
                      <Input id="fullName" defaultValue={user?.display_name || ""} />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input id="email" type="email" defaultValue={user?.email || ""} disabled />
                      <p className="text-xs text-muted-foreground">Email is managed by SSO</p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="phone">Phone</Label>
                      <Input id="phone" type="tel" placeholder="-" />
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

                  <Button>Save Changes</Button>
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
                      <Input id="orgName" defaultValue={user?.org_name || ""} />
                    </div>

                    <div className="space-y-2 md:col-span-2">
                      <Label htmlFor="address">Address</Label>
                      <Textarea id="address" rows={3} placeholder="-" />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="orgPhone">Phone</Label>
                      <Input id="orgPhone" type="tel" placeholder="-" />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="orgEmail">Email</Label>
                      <Input id="orgEmail" type="email" placeholder="-" />
                    </div>
                  </div>

                  <Button>Save Changes</Button>
                </div>

                <div className="border-t border-border" />

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
                    <p className="text-xs text-muted-foreground">v0.10.0</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === "notifications" && <NotificationsSettingsCard />}

        {activeTab === "pipelines" && <PipelinesSettingsCard />}
      </div>
    </div>
  )
}
