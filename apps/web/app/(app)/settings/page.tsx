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
import { CameraIcon, CheckIcon, MonitorIcon, SmartphoneIcon } from "lucide-react"

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("profile")

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
                    {/* Email notifications for new cases */}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="emailNewCases">Email notifications for new cases</Label>
                        <p className="text-sm text-muted-foreground">Get notified when a new case is created</p>
                      </div>
                      <Switch id="emailNewCases" defaultChecked />
                    </div>

                    {/* Email notifications for task reminders */}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="emailTaskReminders">Email notifications for task reminders</Label>
                        <p className="text-sm text-muted-foreground">Get reminded about upcoming tasks</p>
                      </div>
                      <Switch id="emailTaskReminders" defaultChecked />
                    </div>

                    {/* Email notifications for status changes */}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="emailStatusChanges">Email notifications for status changes</Label>
                        <p className="text-sm text-muted-foreground">Get notified when case status changes</p>
                      </div>
                      <Switch id="emailStatusChanges" defaultChecked />
                    </div>

                    {/* Push notifications */}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="pushNotifications">Push notifications (browser)</Label>
                        <p className="text-sm text-muted-foreground">Receive browser push notifications</p>
                      </div>
                      <Switch id="pushNotifications" />
                    </div>

                    {/* Daily digest email */}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="dailyDigest">Daily digest email</Label>
                        <p className="text-sm text-muted-foreground">Receive a daily summary of activity</p>
                      </div>
                      <Switch id="dailyDigest" defaultChecked />
                    </div>

                    {/* Weekly report email */}
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
                  {/* Meta Leads */}
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

                  {/* Google Calendar */}
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

                  {/* Slack */}
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
                  {/* Change Password */}
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
                    {/* Two-factor authentication */}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="twoFactor">Two-factor authentication</Label>
                        <p className="text-sm text-muted-foreground">Add an extra layer of security</p>
                      </div>
                      <Switch id="twoFactor" />
                    </div>
                  </div>

                  <div className="border-t border-border pt-6">
                    {/* Active Sessions */}
                    <h3 className="mb-4 font-medium">Active Sessions</h3>
                    <div className="space-y-3">
                      {/* Session 1 */}
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

                      {/* Session 2 */}
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
                    {/* Delete Account */}
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
          </div>
        </Tabs>
      </div>
    </div>
  )
}