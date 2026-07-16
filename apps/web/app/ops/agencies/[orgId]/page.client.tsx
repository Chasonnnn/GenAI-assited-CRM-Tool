'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import Link from "@/components/app-link";
import {
    getOrganization,
    getSubscription,
    listMembers,
    listInvites,
    getAdminActionLogs,
    getPlatformEmailStatus,
    listAlerts,
    acknowledgeAlert,
    resolveAlert,
    updateSubscription,
    extendSubscription,
    updateMember,
    resetMemberMfa,
    createInvite,
    revokeInvite,
    resendInvite,
    deleteOrganization,
    restoreOrganization,
    purgeOrganization,
    type OrganizationDetail,
    type OrganizationSubscription,
    type OrgMember,
    type OrgInvite,
    type AdminActionLog,
    type PlatformEmailStatus,
} from '@/lib/api/platform';
import { getErrorMessage } from '@/lib/error-utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AgencyOverviewTab } from '@/components/ops/agencies/AgencyOverviewTab';
import { AgencyUsersTab } from '@/components/ops/agencies/AgencyUsersTab';
import { AgencyInvitesTab } from '@/components/ops/agencies/AgencyInvitesTab';
import { AgencySubscriptionTab } from '@/components/ops/agencies/AgencySubscriptionTab';
import { AgencyAlertsTab } from '@/components/ops/agencies/AgencyAlertsTab';
import { AgencyAuditTab } from '@/components/ops/agencies/AgencyAuditTab';
import { SupportSessionDialog } from '@/components/ops/agencies/SupportSessionDialog';
import {
    INVITE_ROLE_OPTIONS,
    PLAN_BADGE_VARIANTS,
    STATUS_BADGE_VARIANTS,
    type InviteRole,
} from '@/components/ops/agencies/agency-constants';
import { ChevronRight, Globe, Copy, Loader2, AlertTriangle } from 'lucide-react';
import { toast } from '@/components/ui/toast';


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

type AgencyDetailData = {
    org: OrganizationDetail;
    subscription: OrganizationSubscription | null;
    members: OrgMember[];
    invites: OrgInvite[];
    actionLogs: AdminActionLog[];
};

function useAgencyDetailController() {
    const params = useParams();
    const orgId = params.orgId as string;
    const { push } = useRouter();
    const queryClient = useQueryClient();
    const agencyDetailQueryKey = ['platform', 'agency', orgId] as const;
    const orgAlertsQueryKey = ['platform', 'alerts', { orgId }] as const;

    const [activeTab, setActiveTab] = useState('overview');
    const [alertsUpdating, setAlertsUpdating] = useState<string | null>(null);
    const [mfaResetting, setMfaResetting] = useState<string | null>(null);
    const [inviteOpen, setInviteOpen] = useState(false);
    const [inviteSubmitting, setInviteSubmitting] = useState(false);
    const [inviteForm, setInviteForm] = useState<{ email: string; role: InviteRole }>({
        email: '',
        role: INVITE_ROLE_OPTIONS[0],
    });
    const [inviteError, setInviteError] = useState<string | null>(null);
    const [inviteResending, setInviteResending] = useState<string | null>(null);
    const [notesDraftOverride, setNotesDraftOverride] = useState<{
        orgId: string;
        value: string;
    } | null>(null);
    const [notesSaving, setNotesSaving] = useState(false);
    const [deleteSubmitting, setDeleteSubmitting] = useState(false);
    const [restoreSubmitting, setRestoreSubmitting] = useState(false);
    const [purgeSubmitting, setPurgeSubmitting] = useState(false);

    const agencyDetailQuery = useQuery({
        queryKey: agencyDetailQueryKey,
        queryFn: async (): Promise<AgencyDetailData> => {
            try {
                const [orgData, subData, membersData, invitesData, logsData] = await Promise.all([
                    getOrganization(orgId),
                    getSubscription(orgId).catch(() => null),
                    listMembers(orgId),
                    listInvites(orgId),
                    getAdminActionLogs(orgId, { limit: 20 }),
                ]);
                return {
                    org: orgData,
                    subscription: subData,
                    members: membersData,
                    invites: invitesData,
                    actionLogs: logsData.items,
                };
            } catch (error) {
                console.error('Failed to fetch agency data:', error);
                toast.error('Failed to load agency details');
                throw error;
            }
        },
        retry: false,
        staleTime: 30_000,
    });
    const agencyDetail = agencyDetailQuery.data;
    const org = agencyDetail?.org ?? null;
    const subscription = agencyDetail?.subscription ?? null;
    const members = agencyDetail?.members ?? [];
    const invites = agencyDetail?.invites ?? [];
    const actionLogs = agencyDetail?.actionLogs ?? [];
    const notesDraft =
        notesDraftOverride?.orgId === orgId
            ? notesDraftOverride.value
            : subscription?.notes ?? '';
    const setNotesDraft = (value: string) => setNotesDraftOverride({ orgId, value });
    const updateAgencyDetail = (
        updater: (current: AgencyDetailData) => AgencyDetailData,
    ) => {
        queryClient.setQueryData<AgencyDetailData>(
            agencyDetailQueryKey,
            (current) => current ? updater(current) : current,
        );
    };

    const alertsQuery = useQuery({
        queryKey: orgAlertsQueryKey,
        queryFn: async () => {
            if (!orgId) return { items: [], total: 0 };
        try {
                return await listAlerts({ org_id: orgId });
        } catch (error) {
                console.error('Failed to fetch org alerts:', error);
                toast.error('Failed to load organization alerts');
                throw error;
        }
        },
        retry: false,
        staleTime: 30_000,
    });
    const orgAlerts = alertsQuery.data?.items ?? [];
    const alertsLoading = alertsQuery.isFetching;
    const fetchOrgAlerts = async () => {
        await alertsQuery.refetch();
    };

    const openAlertCount = orgAlerts.filter((alert) => alert.status === 'open').length;

    const platformEmailQuery = useQuery({
        queryKey: ['platform', 'email-status'],
        queryFn: async () => {
            try {
                return await getPlatformEmailStatus();
            } catch (error) {
                console.error('Failed to fetch platform email status:', error);
                toast.error('Failed to load platform email sender status');
                throw error;
            }
        },
        enabled: activeTab === 'invites',
        retry: false,
        staleTime: 30_000,
    });
    const platformEmailStatus: PlatformEmailStatus | null = platformEmailQuery.data ?? null;
    const platformEmailLoading = platformEmailQuery.isFetching;

    const handleDeleteOrganization = async () => {
        if (!org) return;
        setDeleteSubmitting(true);
        const finishDelete = () => setDeleteSubmitting(false);
        try {
            const updated = await deleteOrganization(org.id);
            updateAgencyDetail((current) => ({ ...current, org: updated }));
            toast.success('Organization scheduled for deletion');
            finishDelete();
        } catch (error) {
            console.error('Failed to delete organization:', error);
            toast.error(getErrorMessage(error, 'Failed to delete organization'));
            finishDelete();
        }
    };

    const handleRestoreOrganization = async () => {
        if (!org) return;
        setRestoreSubmitting(true);
        const finishRestore = () => setRestoreSubmitting(false);
        try {
            const updated = await restoreOrganization(org.id);
            updateAgencyDetail((current) => ({ ...current, org: updated }));
            toast.success('Organization restored');
            finishRestore();
        } catch (error) {
            console.error('Failed to restore organization:', error);
            toast.error(getErrorMessage(error, 'Failed to restore organization'));
            finishRestore();
        }
    };

    const handlePurgeOrganization = async () => {
        if (!org) return;
        setPurgeSubmitting(true);
        const finishPurge = () => setPurgeSubmitting(false);
        try {
            const result = await purgeOrganization(org.id);
            if (result.deleted) {
                toast.success('Organization deleted permanently');
            } else {
                toast.success('Deletion scheduled; org removed from ops list');
            }
            push('/ops/agencies');
            finishPurge();
        } catch (error) {
            console.error('Failed to purge organization:', error);
            toast.error(getErrorMessage(error, 'Failed to delete organization'));
            finishPurge();
        }
    };


    const handleExtendSubscription = async () => {
        try {
            const updated = await extendSubscription(orgId, 30);
            updateAgencyDetail((current) => ({ ...current, subscription: updated }));
            setNotesDraftOverride(null);
            toast.success('Subscription extended by 30 days');
        } catch (error) {
            console.error('Failed to extend subscription:', error);
            toast.error(getErrorMessage(error, 'Failed to extend subscription'));
        }
    };

    const handleResetMfa = async (member: OrgMember) => {
        setMfaResetting(member.id);
        const finishMfaReset = () => setMfaResetting(null);
        try {
            await resetMemberMfa(orgId, member.id);
            toast.success(`MFA and Duo reset for ${member.email}`);
            finishMfaReset();
        } catch (error) {
            console.error('Failed to reset MFA:', error);
            toast.error(getErrorMessage(error, 'Failed to reset MFA and Duo enrollment'));
            finishMfaReset();
        }
    };

    const handleToggleAutoRenew = async (value: boolean) => {
        if (!subscription) return;
        try {
            const updated = await updateSubscription(orgId, { auto_renew: value });
            updateAgencyDetail((current) => ({ ...current, subscription: updated }));
            setNotesDraftOverride(null);
            toast.success(`Auto-renew ${value ? 'enabled' : 'disabled'}`);
        } catch (error) {
            console.error('Failed to update auto-renew setting:', error);
            toast.error(getErrorMessage(error, 'Failed to update auto-renew setting'));
        }
    };

    const handleSaveNotes = async () => {
        if (!subscription) return;
        setNotesSaving(true);
        const finishNotesSave = () => setNotesSaving(false);
        try {
            const updated = await updateSubscription(orgId, { notes: notesDraft });
            updateAgencyDetail((current) => ({ ...current, subscription: updated }));
            setNotesDraftOverride(null);
            toast.success('Subscription notes updated');
            finishNotesSave();
        } catch (error) {
            console.error('Failed to update subscription notes:', error);
            toast.error(getErrorMessage(error, 'Failed to update subscription notes'));
            finishNotesSave();
        }
    };

    const handleDeactivateMember = async (memberId: string) => {
        try {
            await updateMember(orgId, memberId, { is_active: false });
            updateAgencyDetail((current) => ({
                ...current,
                members: current.members.map((member) =>
                    member.id === memberId
                        ? { ...member, is_active: false }
                        : member
                ),
            }));
            toast.success('Member deactivated');
        } catch (error) {
            console.error('Failed to deactivate member:', error);
            toast.error(getErrorMessage(error, 'Failed to deactivate member'));
        }
    };

    const handleRevokeInvite = async (inviteId: string) => {
        try {
            await revokeInvite(orgId, inviteId);
            updateAgencyDetail((current) => ({
                ...current,
                invites: current.invites.map((invite) =>
                    invite.id === inviteId
                        ? { ...invite, status: 'revoked' }
                        : invite
                ),
            }));
            toast.success('Invite revoked');
        } catch (error) {
            console.error('Failed to revoke invite:', error);
            toast.error(getErrorMessage(error, 'Failed to revoke invite'));
        }
    };

    const handleResendInvite = async (inviteId: string) => {
        setInviteResending(inviteId);
        const finishInviteResend = () => setInviteResending(null);
        try {
            await resendInvite(orgId, inviteId);
            const refreshed = await listInvites(orgId);
            updateAgencyDetail((current) => ({ ...current, invites: refreshed }));
            toast.success('Invite resent');
            finishInviteResend();
        } catch (error) {
            console.error('Failed to resend invite:', error);
            toast.error(getErrorMessage(error, 'Failed to resend invite'));
            finishInviteResend();
        }
    };

    const handleCreateInvite = async () => {
        setInviteError(null);
        if (!inviteForm.email.trim()) {
            setInviteError('Email is required');
            return;
        }
        setInviteSubmitting(true);
        const finishInviteCreate = () => setInviteSubmitting(false);
        try {
            const invite = await createInvite(orgId, {
                email: inviteForm.email.trim().toLowerCase(),
                role: inviteForm.role,
            });
            updateAgencyDetail((current) => ({
                ...current,
                invites: [invite, ...current.invites],
            }));
            setInviteOpen(false);
            setInviteForm({ email: '', role: INVITE_ROLE_OPTIONS[0] });
            toast.success('Invite created');
            finishInviteCreate();
        } catch (error) {
            const message = getErrorMessage(error, 'Failed to create invite');
            setInviteError(message);
            finishInviteCreate();
        }
    };

    const handleAcknowledgeAlert = async (alertId: string) => {
        setAlertsUpdating(alertId);
        const finishAlertUpdate = () => setAlertsUpdating(null);
        try {
            await acknowledgeAlert(alertId);
            queryClient.setQueryData<Awaited<ReturnType<typeof listAlerts>>>(
                orgAlertsQueryKey,
                (current) => current
                    ? {
                        ...current,
                        items: current.items.map((alert) =>
                            alert.id === alertId
                                ? { ...alert, status: 'acknowledged' }
                                : alert
                        ),
                    }
                    : current
            );
            toast.success('Alert acknowledged');
            finishAlertUpdate();
        } catch (error) {
            console.error('Failed to acknowledge alert:', error);
            toast.error(getErrorMessage(error, 'Failed to acknowledge alert'));
            finishAlertUpdate();
        }
    };

    const handleResolveAlert = async (alertId: string) => {
        setAlertsUpdating(alertId);
        const finishAlertUpdate = () => setAlertsUpdating(null);
        try {
            const result = await resolveAlert(alertId);
            queryClient.setQueryData<Awaited<ReturnType<typeof listAlerts>>>(
                orgAlertsQueryKey,
                (current) => current
                    ? {
                        ...current,
                        items: current.items.map((alert) =>
                            alert.id === alertId
                                ? {
                                    ...alert,
                                    status: 'resolved',
                                    resolved_at: result.resolved_at,
                                }
                                : alert
                        ),
                    }
                    : current
            );
            toast.success('Alert resolved');
            finishAlertUpdate();
        } catch (error) {
            console.error('Failed to resolve alert:', error);
            toast.error(getErrorMessage(error, 'Failed to resolve alert'));
            finishAlertUpdate();
        }
    };

    const notesDirty = subscription
        ? notesDraft !== (subscription.notes ?? '')
        : false;

    if (agencyDetailQuery.isPending) {
        return { status: 'loading' as const };
    }

    if (!org) {
        return { status: 'missing' as const };
    }

    const isDeleted = Boolean(org.deleted_at);
    const purgeDate = org.purge_at ? new Date(org.purge_at) : null;

    return {
        status: 'ready' as const,
        actionLogs,
        activeTab,
        alertsLoading,
        alertsUpdating,
        deleteSubmitting,
        fetchOrgAlerts,
        handleAcknowledgeAlert,
        handleCreateInvite,
        handleDeactivateMember,
        handleDeleteOrganization,
        handleExtendSubscription,
        handlePurgeOrganization,
        handleResetMfa,
        handleResendInvite,
        handleResolveAlert,
        handleRestoreOrganization,
        handleRevokeInvite,
        handleSaveNotes,
        handleToggleAutoRenew,
        inviteError,
        inviteForm,
        inviteOpen,
        inviteResending,
        inviteSubmitting,
        invites,
        isDeleted,
        members,
        mfaResetting,
        notesDirty,
        notesDraft,
        notesSaving,
        openAlertCount,
        org,
        orgAlerts,
        platformEmailLoading,
        platformEmailStatus,
        purgeDate,
        purgeSubmitting,
        restoreSubmitting,
        setActiveTab,
        setInviteForm,
        setInviteOpen,
        setNotesDraft,
        subscription,
    };
}

type ReadyAgencyDetailController = Extract<
    ReturnType<typeof useAgencyDetailController>,
    { status: 'ready' }
>;

function AgencyDetailLoadingState() {
    return (
        <div className="flex items-center justify-center py-16">
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
    );
}

function AgencyDetailMissingState() {
    return (
        <div className="p-6">
            <div className="text-center py-16">
                <AlertTriangle className="size-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium">Agency not found</h3>
            </div>
        </div>
    );
}

function AgencyDetailHeader({ controller }: { controller: ReadyAgencyDetailController }) {
    const {
        activeTab,
        isDeleted,
        openAlertCount,
        org,
        setActiveTab,
    } = controller;

    return (
        <div className="border-b border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900">
            <div className="px-6 py-4">
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
                            {isDeleted && <Badge variant="destructive">Deletion scheduled</Badge>}
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
                    <div className="flex flex-col items-end gap-2">
                        <Badge
                            variant="outline"
                            className={PLAN_BADGE_VARIANTS[org.subscription_plan]}
                        >
                            {org.subscription_plan} plan
                        </Badge>
                        <SupportSessionDialog
                            orgId={org.id}
                            orgName={org.name}
                            portalBaseUrl={org.portal_base_url}
                            disabled={isDeleted}
                        />
                    </div>
                </div>
            </div>

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
                    <TabsTrigger value="audit">Audit Log</TabsTrigger>
                </TabsList>
            </Tabs>
        </div>
    );
}

function AgencyDetailTabContent({ controller }: { controller: ReadyAgencyDetailController }) {
    const {
        actionLogs,
        activeTab,
        alertsLoading,
        alertsUpdating,
        deleteSubmitting,
        fetchOrgAlerts,
        handleAcknowledgeAlert,
        handleCreateInvite,
        handleDeactivateMember,
        handleDeleteOrganization,
        handleExtendSubscription,
        handlePurgeOrganization,
        handleResetMfa,
        handleResendInvite,
        handleResolveAlert,
        handleRestoreOrganization,
        handleRevokeInvite,
        handleSaveNotes,
        handleToggleAutoRenew,
        inviteError,
        inviteForm,
        inviteOpen,
        inviteResending,
        inviteSubmitting,
        invites,
        isDeleted,
        members,
        mfaResetting,
        notesDirty,
        notesDraft,
        notesSaving,
        org,
        orgAlerts,
        platformEmailLoading,
        platformEmailStatus,
        purgeDate,
        purgeSubmitting,
        restoreSubmitting,
        setActiveTab,
        setInviteForm,
        setInviteOpen,
        setNotesDraft,
        subscription,
    } = controller;

    return (
        <div className="p-6">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsContent value="overview" className="mt-0">
                    <AgencyOverviewTab
                        org={org}
                        isDeleted={isDeleted}
                        purgeDate={purgeDate}
                        restoreSubmitting={restoreSubmitting}
                        deleteSubmitting={deleteSubmitting}
                        onRestoreOrganization={handleRestoreOrganization}
                        onDeleteOrganization={handleDeleteOrganization}
                        purgeSubmitting={purgeSubmitting}
                        onPurgeOrganization={handlePurgeOrganization}
                    />
                </TabsContent>

                <TabsContent value="users" className="mt-0">
                    <AgencyUsersTab
                        members={members}
                        orgName={org.name}
                        mfaResetting={mfaResetting}
                        onResetMfa={handleResetMfa}
                        onDeactivateMember={handleDeactivateMember}
                    />
                </TabsContent>

                <TabsContent value="invites" className="mt-0">
                    <AgencyInvitesTab
                        orgName={org.name}
                        invites={invites}
                        inviteOpen={inviteOpen}
                        inviteSubmitting={inviteSubmitting}
                        inviteResending={inviteResending}
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
                        onResendInvite={handleResendInvite}
                        onRevokeInvite={handleRevokeInvite}
                    />
                </TabsContent>

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

                <TabsContent value="audit" className="mt-0">
                    <AgencyAuditTab actionLogs={actionLogs} />
                </TabsContent>
            </Tabs>
        </div>
    );
}

export default function AgencyDetailPage() {
    const controller = useAgencyDetailController();

    if (controller.status === 'loading') {
        return <AgencyDetailLoadingState />;
    }

    if (controller.status === 'missing') {
        return <AgencyDetailMissingState />;
    }

    return (
        <div>
            <AgencyDetailHeader controller={controller} />
            <AgencyDetailTabContent controller={controller} />
        </div>
    );
}
