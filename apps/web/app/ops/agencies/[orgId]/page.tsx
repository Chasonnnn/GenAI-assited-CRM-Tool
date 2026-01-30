'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from "@/components/app-link";
import {
    getOrganization,
    getSubscription,
    listMembers,
    listInvites,
    getAdminActionLogs,
    getPlatformEmailStatus,
    getOrgSystemEmailTemplate,
    updateOrgSystemEmailTemplate,
    sendTestOrgSystemEmailTemplate,
    listAlerts,
    acknowledgeAlert,
    resolveAlert,
    updateSubscription,
    extendSubscription,
    updateMember,
    resetMemberMfa,
    createInvite,
    revokeInvite,
    deleteOrganization,
    restoreOrganization,
    type SystemEmailTemplate,
    type OrganizationDetail,
    type OrganizationSubscription,
    type OrgMember,
    type OrgInvite,
    type AdminActionLog,
    type PlatformAlert,
    type PlatformEmailStatus,
} from '@/lib/api/platform';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AgencyOverviewTab } from '@/components/ops/agencies/AgencyOverviewTab';
import { AgencyUsersTab } from '@/components/ops/agencies/AgencyUsersTab';
import { AgencyInvitesTab } from '@/components/ops/agencies/AgencyInvitesTab';
import { AgencySubscriptionTab } from '@/components/ops/agencies/AgencySubscriptionTab';
import { AgencyAlertsTab } from '@/components/ops/agencies/AgencyAlertsTab';
import { AgencyTemplatesTab } from '@/components/ops/agencies/AgencyTemplatesTab';
import { AgencyAuditTab } from '@/components/ops/agencies/AgencyAuditTab';
import {
    INVITE_ROLE_OPTIONS,
    PLAN_BADGE_VARIANTS,
    STATUS_BADGE_VARIANTS,
    type InviteRole,
} from '@/components/ops/agencies/agency-constants';
import { ChevronRight, Globe, Copy, Loader2, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const resolveErrorMessage = (error: unknown, fallback: string) => {
    if (error instanceof Error && error.message) {
        return error.message;
    }
    return fallback;
};


function CopyButton({ value, label }: { value: string; label: string }) {
    const handleCopy = async () => {
        await navigator.clipboard.writeText(value);
        toast.success(`${label} copied to clipboard`);
    };

    return (
        <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs text-stone-500"
            onClick={handleCopy}
        >
            <Copy className="size-3 mr-1" />
            Copy ID
        </Button>
    );
}

export default function AgencyDetailPage() {
    const params = useParams();
    const orgId = params.orgId as string;

    const [org, setOrg] = useState<OrganizationDetail | null>(null);
    const [subscription, setSubscription] = useState<OrganizationSubscription | null>(null);
    const [members, setMembers] = useState<OrgMember[]>([]);
    const [invites, setInvites] = useState<OrgInvite[]>([]);
    const [actionLogs, setActionLogs] = useState<AdminActionLog[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('overview');
    const [openAlertCount, setOpenAlertCount] = useState(0);
    const [orgAlerts, setOrgAlerts] = useState<PlatformAlert[]>([]);
    const [alertsLoading, setAlertsLoading] = useState(false);
    const [alertsUpdating, setAlertsUpdating] = useState<string | null>(null);
    const [mfaResetting, setMfaResetting] = useState<string | null>(null);
    const [inviteOpen, setInviteOpen] = useState(false);
    const [inviteSubmitting, setInviteSubmitting] = useState(false);
    const [inviteForm, setInviteForm] = useState<{ email: string; role: InviteRole }>({
        email: '',
        role: INVITE_ROLE_OPTIONS[0],
    });
    const [inviteError, setInviteError] = useState<string | null>(null);
    const [notesDraft, setNotesDraft] = useState('');
    const [notesSaving, setNotesSaving] = useState(false);
    const subscriptionNotes = subscription?.notes ?? '';
    const [platformEmailStatus, setPlatformEmailStatus] = useState<PlatformEmailStatus | null>(null);
    const [platformEmailLoading, setPlatformEmailLoading] = useState(false);
    const [inviteTemplate, setInviteTemplate] = useState<SystemEmailTemplate | null>(null);
    const [inviteTemplateLoading, setInviteTemplateLoading] = useState(false);
    const [inviteTemplateSaving, setInviteTemplateSaving] = useState(false);
    const [templateSubject, setTemplateSubject] = useState('');
    const [templateFromEmail, setTemplateFromEmail] = useState('');
    const [templateBody, setTemplateBody] = useState('');
    const [templateActive, setTemplateActive] = useState(true);
    const [templateVersion, setTemplateVersion] = useState<number | null>(null);
    const [testEmail, setTestEmail] = useState('');
    const [testSending, setTestSending] = useState(false);
    const [deleteSubmitting, setDeleteSubmitting] = useState(false);
    const [restoreSubmitting, setRestoreSubmitting] = useState(false);

    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            try {
                const [orgData, subData, membersData, invitesData, logsData] = await Promise.all([
                    getOrganization(orgId),
                    getSubscription(orgId).catch(() => null),
                    listMembers(orgId),
                    listInvites(orgId),
                    getAdminActionLogs(orgId, { limit: 20 }),
                ]);
                setOrg(orgData);
                setSubscription(subData);
                setMembers(membersData);
                setInvites(invitesData);
                setActionLogs(logsData.items);
            } catch (error) {
                console.error('Failed to fetch agency data:', error);
                toast.error('Failed to load agency details');
            } finally {
                setIsLoading(false);
            }
        }
        fetchData();
    }, [orgId]);

    useEffect(() => {
        setNotesDraft(subscriptionNotes);
    }, [subscriptionNotes]);

    const fetchOrgAlerts = useCallback(async () => {
        if (!orgId) return;
        setAlertsLoading(true);
        try {
            const data = await listAlerts({ org_id: orgId });
            setOrgAlerts(data.items);
        } catch (error) {
            console.error('Failed to fetch org alerts:', error);
            toast.error('Failed to load organization alerts');
            setOpenAlertCount(0);
        } finally {
            setAlertsLoading(false);
        }
    }, [orgId]);

    useEffect(() => {
        fetchOrgAlerts();
    }, [fetchOrgAlerts]);

    useEffect(() => {
        setOpenAlertCount(
            orgAlerts.filter((alert) => alert.status === 'open').length
        );
    }, [orgAlerts]);

    useEffect(() => {
        if (activeTab !== 'templates' && activeTab !== 'invites') return;

        async function fetchEmailStatus() {
            setPlatformEmailLoading(true);
            try {
                const status = await getPlatformEmailStatus();
                setPlatformEmailStatus(status);
            } catch (error) {
                console.error('Failed to fetch platform email status:', error);
                toast.error('Failed to load platform email sender status');
            } finally {
                setPlatformEmailLoading(false);
            }
        }

        fetchEmailStatus();
        if (activeTab === 'templates') {
            async function fetchInviteTemplate() {
                setInviteTemplateLoading(true);
                try {
                    const tpl = await getOrgSystemEmailTemplate(orgId, 'org_invite');
                    setInviteTemplate(tpl);
                    setTemplateSubject(tpl.subject);
                    setTemplateFromEmail(tpl.from_email || '');
                    setTemplateBody(tpl.body);
                    setTemplateActive(tpl.is_active);
                    setTemplateVersion(tpl.current_version);
                } catch (error) {
                    console.error('Failed to fetch invite template:', error);
                    toast.error('Failed to load invite email template');
                } finally {
                    setInviteTemplateLoading(false);
                }
            }

            fetchInviteTemplate();
        }
    }, [activeTab, orgId]);

    const handleSaveInviteTemplate = async () => {
        setInviteTemplateSaving(true);
        try {
            const payload: Parameters<typeof updateOrgSystemEmailTemplate>[2] = {
                subject: templateSubject,
                from_email: templateFromEmail.trim() ? templateFromEmail.trim() : null,
                body: templateBody,
                is_active: templateActive,
            };
            if (templateVersion !== null) {
                payload.expected_version = templateVersion;
            }

            const updated = await updateOrgSystemEmailTemplate(orgId, 'org_invite', payload);
            setInviteTemplate(updated);
            setTemplateSubject(updated.subject);
            setTemplateFromEmail(updated.from_email || '');
            setTemplateBody(updated.body);
            setTemplateActive(updated.is_active);
            setTemplateVersion(updated.current_version);
            toast.success('Invite email template updated');
        } catch (error) {
            console.error('Failed to update invite template:', error);
            toast.error(resolveErrorMessage(error, 'Failed to update invite email template'));
        } finally {
            setInviteTemplateSaving(false);
        }
    };

    const handleSendTestInviteEmail = async () => {
        if (!testEmail) return;
        setTestSending(true);
        try {
            await sendTestOrgSystemEmailTemplate(orgId, 'org_invite', { to_email: testEmail });
            toast.success('Test email sent');
        } catch (error) {
            console.error('Failed to send test email:', error);
            toast.error(resolveErrorMessage(error, 'Failed to send test email'));
        } finally {
            setTestSending(false);
        }
    };

    const handleDeleteOrganization = async () => {
        if (!org) return;
        setDeleteSubmitting(true);
        try {
            const updated = await deleteOrganization(org.id);
            setOrg(updated);
            toast.success('Organization scheduled for deletion');
        } catch (error) {
            console.error('Failed to delete organization:', error);
            toast.error(resolveErrorMessage(error, 'Failed to delete organization'));
        } finally {
            setDeleteSubmitting(false);
        }
    };

    const handleRestoreOrganization = async () => {
        if (!org) return;
        setRestoreSubmitting(true);
        try {
            const updated = await restoreOrganization(org.id);
            setOrg(updated);
            toast.success('Organization restored');
        } catch (error) {
            console.error('Failed to restore organization:', error);
            toast.error(resolveErrorMessage(error, 'Failed to restore organization'));
        } finally {
            setRestoreSubmitting(false);
        }
    };

    const handleGoToTemplates = () => {
        setInviteOpen(false);
        setActiveTab('templates');
    };

    const handleExtendSubscription = async () => {
        try {
            const updated = await extendSubscription(orgId, 30);
            setSubscription(updated);
            toast.success('Subscription extended by 30 days');
        } catch {
            toast.error('Failed to extend subscription');
        }
    };

    const handleResetMfa = async (member: OrgMember) => {
        setMfaResetting(member.id);
        try {
            await resetMemberMfa(orgId, member.id);
            toast.success(`MFA reset for ${member.email}`);
        } catch (error) {
            console.error('Failed to reset MFA:', error);
            toast.error('Failed to reset MFA');
        } finally {
            setMfaResetting(null);
        }
    };

    const handleToggleAutoRenew = async (value: boolean) => {
        if (!subscription) return;
        try {
            const updated = await updateSubscription(orgId, { auto_renew: value });
            setSubscription(updated);
            toast.success(`Auto-renew ${value ? 'enabled' : 'disabled'}`);
        } catch {
            toast.error('Failed to update auto-renew setting');
        }
    };

    const handleSaveNotes = async () => {
        if (!subscription) return;
        setNotesSaving(true);
        try {
            const updated = await updateSubscription(orgId, { notes: notesDraft });
            setSubscription(updated);
            toast.success('Subscription notes updated');
        } catch {
            toast.error('Failed to update subscription notes');
        } finally {
            setNotesSaving(false);
        }
    };

    const handleDeactivateMember = async (memberId: string) => {
        try {
            await updateMember(orgId, memberId, { is_active: false });
            setMembers((prev) =>
                prev.map((m) => (m.id === memberId ? { ...m, is_active: false } : m))
            );
            toast.success('Member deactivated');
        } catch {
            toast.error('Failed to deactivate member');
        }
    };

    const handleRevokeInvite = async (inviteId: string) => {
        try {
            await revokeInvite(orgId, inviteId);
            setInvites((prev) =>
                prev.map((i) => (i.id === inviteId ? { ...i, status: 'revoked' } : i))
            );
            toast.success('Invite revoked');
        } catch {
            toast.error('Failed to revoke invite');
        }
    };

    const handleCreateInvite = async () => {
        setInviteError(null);
        if (!inviteForm.email.trim()) {
            setInviteError('Email is required');
            return;
        }
        setInviteSubmitting(true);
        try {
            const invite = await createInvite(orgId, {
                email: inviteForm.email.trim().toLowerCase(),
                role: inviteForm.role,
            });
            setInvites((prev) => [invite, ...prev]);
            setInviteOpen(false);
            setInviteForm({ email: '', role: INVITE_ROLE_OPTIONS[0] });
            toast.success('Invite created');
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to create invite';
            setInviteError(message);
        } finally {
            setInviteSubmitting(false);
        }
    };

    const handleAcknowledgeAlert = async (alertId: string) => {
        setAlertsUpdating(alertId);
        try {
            await acknowledgeAlert(alertId);
            setOrgAlerts((prev) =>
                prev.map((alert) =>
                    alert.id === alertId ? { ...alert, status: 'acknowledged' } : alert
                )
            );
            toast.success('Alert acknowledged');
        } catch {
            toast.error('Failed to acknowledge alert');
        } finally {
            setAlertsUpdating(null);
        }
    };

    const handleResolveAlert = async (alertId: string) => {
        setAlertsUpdating(alertId);
        try {
            const result = await resolveAlert(alertId);
            setOrgAlerts((prev) =>
                prev.map((alert) =>
                    alert.id === alertId
                        ? { ...alert, status: 'resolved', resolved_at: result.resolved_at }
                        : alert
                )
            );
            toast.success('Alert resolved');
        } catch {
            toast.error('Failed to resolve alert');
        } finally {
            setAlertsUpdating(null);
        }
    };

    const notesDirty = subscription
        ? notesDraft !== (subscription.notes ?? '')
        : false;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!org) {
        return (
            <div className="p-6">
                <div className="text-center py-16">
                    <AlertTriangle className="size-12 mx-auto mb-4 text-muted-foreground/50" />
                    <h3 className="text-lg font-medium">Agency not found</h3>
                </div>
            </div>
        );
    }

    const isDeleted = Boolean(org.deleted_at);
    const purgeDate = org.purge_at ? new Date(org.purge_at) : null;

    return (
        <div>
            {/* Header */}
            <div className="border-b border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900">
                <div className="px-6 py-4">
                    {/* Breadcrumb */}
                    <div className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400 mb-2">
                        <Link
                            href="/ops/agencies"
                            className="hover:text-stone-900 dark:hover:text-stone-100"
                        >
                            Agencies
                        </Link>
                        <ChevronRight className="size-4" />
                        <span className="text-stone-900 dark:text-stone-100">{org.name}</span>
                    </div>

                    {/* Header Content */}
                    <div className="flex items-start justify-between">
                        <div>
                            <div className="flex items-center gap-3">
                                <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                                    {org.name}
                                </h1>
                                <Badge
                                    variant="outline"
                                    className={STATUS_BADGE_VARIANTS[org.subscription_status]}
                                >
                                    {org.subscription_status}
                                </Badge>
                                {isDeleted && (
                                    <Badge variant="destructive">Deletion scheduled</Badge>
                                )}
                            </div>
                            <div className="flex items-center gap-4 mt-1 text-sm text-stone-500 dark:text-stone-400">
                                <span className="font-mono">{org.slug}</span>
                                <CopyButton value={org.id} label="ID" />
                                {org.portal_base_url && (
                                    <a
                                        href={org.portal_base_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-1 hover:text-primary transition-colors"
                                    >
                                        <Globe className="size-3.5" />
                                        {org.portal_base_url.replace('https://', '')}
                                    </a>
                                )}
                            </div>
                        </div>
                        <Badge variant="outline" className={PLAN_BADGE_VARIANTS[org.subscription_plan]}>
                            {org.subscription_plan} plan
                        </Badge>
                    </div>
                </div>

                {/* Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab} className="px-6">
                    <TabsList className="border-b-0">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="users">
                            Users{' '}
                            <Badge variant="secondary" className="ml-1.5">
                                {org.member_count}
                            </Badge>
                        </TabsTrigger>
                        <TabsTrigger value="invites">Invites</TabsTrigger>
                        <TabsTrigger value="subscription">Subscription</TabsTrigger>
                        <TabsTrigger value="alerts">
                            Alerts
                            {openAlertCount > 0 && (
                                <Badge variant="destructive" className="ml-1.5">
                                    {openAlertCount}
                                </Badge>
                            )}
                        </TabsTrigger>
                        <TabsTrigger value="templates">Templates</TabsTrigger>
                        <TabsTrigger value="audit">Audit Log</TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>

            {/* Tab Content */}
            <div className="p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    {/* Overview Tab */}
                    <TabsContent value="overview" className="mt-0">
                        <AgencyOverviewTab
                            org={org}
                            isDeleted={isDeleted}
                            purgeDate={purgeDate}
                            restoreSubmitting={restoreSubmitting}
                            deleteSubmitting={deleteSubmitting}
                            onRestoreOrganization={handleRestoreOrganization}
                            onDeleteOrganization={handleDeleteOrganization}
                        />
                    </TabsContent>

                    {/* Users Tab */}
                    <TabsContent value="users" className="mt-0">
                        <AgencyUsersTab
                            members={members}
                            orgName={org.name}
                            mfaResetting={mfaResetting}
                            onResetMfa={handleResetMfa}
                            onDeactivateMember={handleDeactivateMember}
                        />
                    </TabsContent>

                    {/* Invites Tab */}
                    <TabsContent value="invites" className="mt-0">
                        <AgencyInvitesTab
                            orgName={org.name}
                            invites={invites}
                            inviteOpen={inviteOpen}
                            inviteSubmitting={inviteSubmitting}
                            inviteForm={inviteForm}
                            inviteError={inviteError}
                            platformEmailStatus={platformEmailStatus}
                            platformEmailLoading={platformEmailLoading}
                            onInviteOpenChange={setInviteOpen}
                            onInviteEmailChange={(email) =>
                                setInviteForm((prev) => ({ ...prev, email }))
                            }
                            onInviteRoleChange={(role) =>
                                setInviteForm((prev) => ({ ...prev, role }))
                            }
                            onCreateInvite={handleCreateInvite}
                            onRevokeInvite={handleRevokeInvite}
                            onGoToTemplates={handleGoToTemplates}
                        />
                    </TabsContent>

                    {/* Subscription Tab */}
                    <TabsContent value="subscription" className="mt-0 space-y-6">
                        <AgencySubscriptionTab
                            subscription={subscription}
                            notesDraft={notesDraft}
                            notesDirty={notesDirty}
                            notesSaving={notesSaving}
                            onNotesChange={setNotesDraft}
                            onSaveNotes={handleSaveNotes}
                            onExtendSubscription={handleExtendSubscription}
                            onToggleAutoRenew={handleToggleAutoRenew}
                        />
                    </TabsContent>

                    {/* Alerts Tab */}
                    <TabsContent value="alerts" className="mt-0">
                        <AgencyAlertsTab
                            orgAlerts={orgAlerts}
                            alertsLoading={alertsLoading}
                            alertsUpdating={alertsUpdating}
                            onRefresh={fetchOrgAlerts}
                            onAcknowledge={handleAcknowledgeAlert}
                            onResolve={handleResolveAlert}
                        />
                    </TabsContent>

                    {/* Templates Tab */}
                    <TabsContent value="templates" className="mt-0">
                        <AgencyTemplatesTab
                            orgName={org.name}
                            portalBaseUrl={org.portal_base_url}
                            platformEmailStatus={platformEmailStatus}
                            platformEmailLoading={platformEmailLoading}
                            inviteTemplate={inviteTemplate}
                            inviteTemplateLoading={inviteTemplateLoading}
                            templateFromEmail={templateFromEmail}
                            templateSubject={templateSubject}
                            templateBody={templateBody}
                            templateActive={templateActive}
                            templateVersion={templateVersion}
                            onTemplateFromEmailChange={setTemplateFromEmail}
                            onTemplateSubjectChange={setTemplateSubject}
                            onTemplateBodyChange={setTemplateBody}
                            onTemplateActiveChange={setTemplateActive}
                            onSaveTemplate={handleSaveInviteTemplate}
                            inviteTemplateSaving={inviteTemplateSaving}
                            testEmail={testEmail}
                            onTestEmailChange={setTestEmail}
                            onSendTestEmail={handleSendTestInviteEmail}
                            testSending={testSending}
                        />
                    </TabsContent>

                    {/* Audit Log Tab */}
                    <TabsContent value="audit" className="mt-0">
                        <AgencyAuditTab actionLogs={actionLogs} />
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
}
