"use client"

import { useState } from "react"
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  CameraIcon,
  CheckIcon,
  ChevronDownIcon,
  CopyIcon,
  LoaderIcon,
  MailIcon,
  MonitorIcon,
  MoreVerticalIcon,
  PlusIcon,
  SmartphoneIcon,
  TrashIcon,
} from "lucide-react"
import {
  useEmailTemplates,
  useCreateEmailTemplate,
  useUpdateEmailTemplate,
  useDeleteEmailTemplate,
} from "@/lib/hooks/use-email-templates"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("profile")
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)
  const [isVariablesOpen, setIsVariablesOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplateListItem | null>(null)
  const [showInactive, setShowInactive] = useState(false)

  // Form state
  const [templateName, setTemplateName] = useState("")
  const [templateSubject, setTemplateSubject] = useState("")
  const [templateBody, setTemplateBody] = useState("")
  const [templateActive, setTemplateActive] = useState(true)

  // API hooks
  const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates(!showInactive)
  const createMutation = useCreateEmailTemplate()
  const updateMutation = useUpdateEmailTemplate()
  const deleteMutation = useDeleteEmailTemplate()

  const resetForm = () => {
    setTemplateName("")
    setTemplateSubject("")
    setTemplateBody("")
    setTemplateActive(true)
    setEditingTemplate(null)
  }

  const openCreateModal = () => {
    resetForm()
    setIsTemplateModalOpen(true)
  }

  const openEditModal = (template: EmailTemplateListItem) => {
    setEditingTemplate(template)
    setTemplateName(template.name)
    setTemplateSubject(template.subject)
    setTemplateBody("") // Would need to fetch full template for body
    setTemplateActive(template.is_active)
    setIsTemplateModalOpen(true)
  }

  const handleSaveTemplate = async () => {
    if (editingTemplate) {
      await updateMutation.mutateAsync({
        id: editingTemplate.id,
        data: {
          name: templateName,
          subject: templateSubject,
          body: templateBody || undefined,
          is_active: templateActive,
        },
      })
    } else {
      await createMutation.mutateAsync({
        name: templateName,
        subject: templateSubject,
        body: templateBody,
      })
    }
    setIsTemplateModalOpen(false)
    resetForm()
  }

  const handleDeleteTemplate = async (id: string) => {
    if (confirm("Are you sure you want to delete this template?")) {
      await deleteMutation.mutateAsync(id)
    }
  }

  const insertVariable = (variable: string) => {
    setTemplateSubject(prev => prev + variable)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return "Today"
    if (diffDays === 1) return "Yesterday"
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    return date.toLocaleDateString()
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
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col gap-6 lg:flex-row">
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
                  value="email-templates"
                  className="justify-start data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  Email Templates
                </TabsTrigger>
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
              <Card>
                <CardHeader>
                  <CardTitle>Notification Preferences</CardTitle>
                  <CardDescription>Manage how you receive notifications</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="emailNewCases">Email notifications for new cases</Label>
                        <p className="text-sm text-muted-foreground">Get notified when a new case is created</p>
                      </div>
                      <Switch id="emailNewCases" defaultChecked />
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="emailTaskReminders">Email notifications for task reminders</Label>
                        <p className="text-sm text-muted-foreground">Get reminded about upcoming tasks</p>
                      </div>
                      <Switch id="emailTaskReminders" defaultChecked />
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="emailStatusChanges">Email notifications for status changes</Label>
                        <p className="text-sm text-muted-foreground">Get notified when case status changes</p>
                      </div>
                      <Switch id="emailStatusChanges" defaultChecked />
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="pushNotifications">Push notifications (browser)</Label>
                        <p className="text-sm text-muted-foreground">Receive browser push notifications</p>
                      </div>
                      <Switch id="pushNotifications" />
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="dailyDigest">Daily digest email</Label>
                        <p className="text-sm text-muted-foreground">Receive a daily summary of activity</p>
                      </div>
                      <Switch id="dailyDigest" defaultChecked />
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="weeklyReport">Weekly report email</Label>
                        <p className="text-sm text-muted-foreground">Receive a weekly performance report</p>
                      </div>
                      <Switch id="weeklyReport" />
                    </div>
                  </div>
                </CardContent>
              </Card>
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

            {/* Email Templates Tab */}
            <TabsContent value="email-templates" className="mt-0">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Email Templates</CardTitle>
                      <CardDescription>Manage email templates for automated communications</CardDescription>
                    </div>
                    <Dialog open={isTemplateModalOpen} onOpenChange={(open) => {
                      setIsTemplateModalOpen(open)
                      if (!open) resetForm()
                    }}>
                      <DialogTrigger asChild>
                        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openCreateModal}>
                          <PlusIcon className="mr-2 size-4" />
                          New Template
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-2xl">
                        <DialogHeader>
                          <DialogTitle>{editingTemplate ? "Edit Template" : "Create Email Template"}</DialogTitle>
                          <DialogDescription>
                            {editingTemplate ? "Update your email template" : "Create a new email template for automated communications"}
                          </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-4">
                          <div className="space-y-2">
                            <Label htmlFor="template-name">
                              Template Name <span className="text-destructive">*</span>
                            </Label>
                            <Input
                              id="template-name"
                              placeholder="e.g., Welcome Email"
                              value={templateName}
                              onChange={(e) => setTemplateName(e.target.value)}
                            />
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="subject">
                              Subject Line <span className="text-destructive">*</span>
                            </Label>
                            <div className="flex gap-2">
                              <Input
                                id="subject"
                                placeholder="e.g., Welcome to {{organization_name}}"
                                className="flex-1"
                                value={templateSubject}
                                onChange={(e) => setTemplateSubject(e.target.value)}
                              />
                              <Select onValueChange={insertVariable}>
                                <SelectTrigger className="w-[180px]">
                                  <SelectValue placeholder="Insert variable" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="{{full_name}}">{"{{full_name}}"}</SelectItem>
                                  <SelectItem value="{{case_number}}">{"{{case_number}}"}</SelectItem>
                                  <SelectItem value="{{status}}">{"{{status}}"}</SelectItem>
                                  <SelectItem value="{{organization_name}}">{"{{organization_name}}"}</SelectItem>
                                  <SelectItem value="{{agent_name}}">{"{{agent_name}}"}</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="body">Email Body</Label>
                            <Textarea
                              id="body"
                              rows={8}
                              placeholder="Write your email template here. Use variables like {{full_name}}, {{case_number}}, etc."
                              value={templateBody}
                              onChange={(e) => setTemplateBody(e.target.value)}
                            />
                          </div>

                          <Collapsible open={isVariablesOpen} onOpenChange={setIsVariablesOpen}>
                            <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm font-medium hover:bg-muted">
                              Available Variables
                              <ChevronDownIcon
                                className={`size-4 transition-transform ${isVariablesOpen ? "rotate-180" : ""}`}
                              />
                            </CollapsibleTrigger>
                            <CollapsibleContent className="mt-2 space-y-2 rounded-lg border border-border bg-muted/30 p-4">
                              <p className="text-xs text-muted-foreground mb-3">
                                Click to copy a variable to your clipboard:
                              </p>
                              <div className="grid grid-cols-2 gap-2">
                                {[
                                  { var: "{{full_name}}", desc: "Recipient's full name" },
                                  { var: "{{first_name}}", desc: "Recipient's first name" },
                                  { var: "{{case_number}}", desc: "Case number" },
                                  { var: "{{status}}", desc: "Case status" },
                                  { var: "{{organization_name}}", desc: "Your organization name" },
                                  { var: "{{agent_name}}", desc: "Assigned agent name" },
                                ].map((item) => (
                                  <button
                                    key={item.var}
                                    onClick={() => navigator.clipboard.writeText(item.var)}
                                    className="flex items-start gap-2 rounded-lg border border-border bg-background px-3 py-2 text-left hover:bg-accent"
                                  >
                                    <code className="text-xs font-mono text-teal-600">{item.var}</code>
                                    <div className="flex-1">
                                      <p className="text-xs text-muted-foreground">{item.desc}</p>
                                    </div>
                                    <CopyIcon className="size-3 text-muted-foreground" />
                                  </button>
                                ))}
                              </div>
                            </CollapsibleContent>
                          </Collapsible>

                          <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
                            <div className="space-y-0.5">
                              <Label htmlFor="active-toggle">Active</Label>
                              <p className="text-xs text-muted-foreground">
                                Enable this template for automated emails
                              </p>
                            </div>
                            <Switch
                              id="active-toggle"
                              checked={templateActive}
                              onCheckedChange={setTemplateActive}
                            />
                          </div>
                        </div>

                        <DialogFooter>
                          <Button variant="outline" onClick={() => setIsTemplateModalOpen(false)}>
                            Cancel
                          </Button>
                          <Button
                            className="bg-teal-600 hover:bg-teal-700"
                            onClick={handleSaveTemplate}
                            disabled={createMutation.isPending || updateMutation.isPending || !templateName || !templateSubject}
                          >
                            {(createMutation.isPending || updateMutation.isPending) && (
                              <LoaderIcon className="mr-2 size-4 animate-spin" />
                            )}
                            {editingTemplate ? "Update Template" : "Save Template"}
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardHeader>
                <CardContent>
                  {templatesLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                      <span className="ml-2 text-muted-foreground">Loading templates...</span>
                    </div>
                  ) : templates.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                      <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
                        <MailIcon className="size-8 text-muted-foreground" />
                      </div>
                      <h3 className="mb-2 text-lg font-medium">No email templates yet</h3>
                      <p className="mb-4 text-sm text-muted-foreground">Create your first template to get started</p>
                      <Button className="bg-teal-600 hover:bg-teal-700" onClick={openCreateModal}>
                        <PlusIcon className="mr-2 size-4" />
                        Create Template
                      </Button>
                    </div>
                  ) : (
                    <div className="grid gap-4 md:grid-cols-2">
                      {templates.map((template) => (
                        <Card key={template.id} className="group relative hover:shadow-md transition-shadow">
                          <CardContent className="p-4">
                            <div className="mb-3 flex items-start justify-between">
                              <div className="flex-1">
                                <h3 className="font-medium">{template.name}</h3>
                                <p className="mt-1 text-sm text-muted-foreground line-clamp-1">{template.subject}</p>
                              </div>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8 p-0"
                                  >
                                    <MoreVerticalIcon className="size-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => openEditModal(template)}>
                                    Edit
                                  </DropdownMenuItem>
                                  <DropdownMenuItem>
                                    <CopyIcon className="mr-2 size-4" />
                                    Duplicate
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    className="text-destructive"
                                    onClick={() => handleDeleteTemplate(template.id)}
                                  >
                                    <TrashIcon className="mr-2 size-4" />
                                    Delete
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                            <div className="flex items-center justify-between">
                              <Badge
                                className={
                                  template.is_active
                                    ? "bg-green-500/10 text-green-500 border-green-500/20"
                                    : "bg-gray-500/10 text-gray-500 border-gray-500/20"
                                }
                              >
                                {template.is_active ? "Active" : "Inactive"}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                Updated {formatDate(template.updated_at)}
                              </span>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  )
}