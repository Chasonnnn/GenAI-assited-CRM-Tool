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
    type PlatformEmailStatus,
    type SystemEmailTemplate,
    type OrganizationDetail,
    type OrganizationSubscription,
    type OrgMember,
    type OrgInvite,
    type AdminActionLog,
    type PlatformAlert,
} from '@/lib/api/platform';
import { Button, buttonVariants } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
    DialogTrigger,
} from '@/components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    ChevronRight,
    Globe,
    Copy,
    Loader2,
    AlertTriangle,
    CalendarPlus,
    UserMinus,
    Mail,
    Ban,
    ShieldOff,
    Code,
    Plus,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import DOMPurify from 'dompurify';
import { toast } from 'sonner';
import { RichTextEditor } from '@/components/rich-text-editor';

const STATUS_BADGE_VARIANTS: Record<string, string> = {
    active: 'bg-green-500/10 text-green-600 border-green-500/20',
    trial: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    past_due: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    canceled: 'bg-red-500/10 text-red-600 border-red-500/20',
};

const PLAN_BADGE_VARIANTS: Record<string, string> = {
    starter: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300',
    professional: 'bg-teal-500/10 text-teal-600 dark:text-teal-400',
    enterprise: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
};

const INVITE_STATUS_VARIANTS: Record<string, string> = {
    pending: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    accepted: 'bg-green-500/10 text-green-600 border-green-500/20',
    expired: 'bg-stone-500/10 text-stone-600 border-stone-500/20',
    revoked: 'bg-red-500/10 text-red-600 border-red-500/20',
};

const INVITE_ROLE_OPTIONS = ['intake_specialist', 'case_manager', 'admin', 'developer'] as const;
type InviteRole = (typeof INVITE_ROLE_OPTIONS)[number];
const INVITE_ROLE_LABELS: Record<InviteRole, string> = {
    intake_specialist: 'Intake Specialist',
    case_manager: 'Case Manager',
    admin: 'Admin',
    developer: 'Developer',
};

const resolveErrorMessage = (error: unknown, fallback: string) => {
    if (error instanceof Error && error.message) {
        return error.message;
    }
    return fallback;
};

const ALERT_STATUS_BADGES: Record<string, string> = {
    open: 'bg-red-500/10 text-red-600 border-red-500/20',
    acknowledged: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    resolved: 'bg-green-500/10 text-green-600 border-green-500/20',
};

const ALERT_SEVERITY_BADGES: Record<string, string> = {
    critical: 'bg-red-500/10 text-red-600 border-red-500/20',
    error: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
    warn: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    info: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
};

function DetailRow({
    label,
    value,
    mono = false,
}: {
    label: string;
    value: string | null | undefined;
    mono?: boolean;
}) {
    return (
        <div className="flex justify-between py-2 border-b border-stone-100 dark:border-stone-800 last:border-0">
            <span className="text-stone-500 dark:text-stone-400">{label}</span>
            <span
                className={`text-stone-900 dark:text-stone-100 ${mono ? 'font-mono text-sm' : ''}`}
            >
                {value || '-'}
            </span>
        </div>
    );
}

function StatBlock({ label, value }: { label: string; value: number }) {
    return (
        <div className="text-center p-4 bg-stone-50 dark:bg-stone-800/50 rounded-lg">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
                {value.toLocaleString()}
            </div>
            <div className="text-xs text-stone-500 dark:text-stone-400 mt-1">{label}</div>
        </div>
    );
}

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
    const [deleteOpen, setDeleteOpen] = useState(false);
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
            setDeleteOpen(false);
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

    const previewSubject = templateSubject.replace(/\{\{org_name\}\}/g, org?.name ?? 'Organization');
    const previewBody = DOMPurify.sanitize(
        templateBody
            .replace(/\{\{org_name\}\}/g, org?.name ?? 'Organization')
            .replace(/\{\{inviter_text\}\}/g, ' by Platform Admin')
            .replace(/\{\{role_title\}\}/g, 'Admin')
            .replace(
                /\{\{invite_url\}\}/g,
                `${org?.portal_base_url || 'https://app.example.com'}/invite/EXAMPLE`
            )
            .replace(/\{\{expires_block\}\}/g, '<p>This invitation expires in 7 days.</p>'),
        {
            USE_PROFILES: { html: true },
            ADD_TAGS: [
                'table',
                'thead',
                'tbody',
                'tfoot',
                'tr',
                'td',
                'th',
                'colgroup',
                'col',
                'img',
                'hr',
                'div',
                'span',
                'center',
                'h1',
                'h2',
                'h3',
                'h4',
                'h5',
                'h6',
            ],
            ADD_ATTR: [
                'style',
                'class',
                'align',
                'valign',
                'width',
                'height',
                'cellpadding',
                'cellspacing',
                'border',
                'bgcolor',
                'colspan',
                'rowspan',
                'role',
                'target',
                'rel',
                'href',
                'src',
                'alt',
                'title',
            ],
        }
    );

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
                        <div className="grid gap-6 md:grid-cols-2">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg">Organization Details</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-1">
                                    <DetailRow label="Name" value={org.name} />
                                    <DetailRow label="Slug" value={org.slug} mono />
                                    <DetailRow label="Timezone" value={org.timezone} />
                                    <DetailRow
                                        label="Created"
                                        value={format(new Date(org.created_at), 'MMMM d, yyyy')}
                                    />
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg">Statistics</CardTitle>
                                </CardHeader>
                                <CardContent className="grid grid-cols-2 gap-4">
                                    <StatBlock label="Members" value={org.member_count} />
                                    <StatBlock label="Surrogates" value={org.surrogate_count} />
                                    <StatBlock label="Active Matches" value={org.active_match_count} />
                                    <StatBlock label="Tasks Pending" value={org.pending_task_count} />
                                </CardContent>
                            </Card>
                        </div>

                        <Card className="mt-6 border-destructive/30">
                            <CardHeader>
                                <CardTitle className="text-lg text-destructive">
                                    Danger Zone
                                </CardTitle>
                                <CardDescription>
                                    Soft delete this organization for 30 days, then permanently remove all data.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {isDeleted ? (
                                    <div className="space-y-3">
                                        <div className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-900 dark:border-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-100">
                                            Deletion scheduled{purgeDate ? ` for ${format(purgeDate, 'MMM d, yyyy h:mm a')}` : ''}.
                                        </div>
                                        <Button
                                            variant="outline"
                                            onClick={handleRestoreOrganization}
                                            disabled={restoreSubmitting}
                                        >
                                            {restoreSubmitting ? (
                                                <Loader2 className="mr-2 size-4 animate-spin" />
                                            ) : null}
                                            Restore Organization
                                        </Button>
                                    </div>
                                ) : (
                                    <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
                                        <AlertDialogTrigger
                                            className={buttonVariants({
                                                variant: 'destructive',
                                            })}
                                        >
                                            Delete Organization
                                        </AlertDialogTrigger>
                                        <AlertDialogContent>
                                            <AlertDialogHeader>
                                                <AlertDialogTitle>
                                                    Delete {org.name}?
                                                </AlertDialogTitle>
                                                <AlertDialogDescription>
                                                    This will disable access immediately. Data will be permanently deleted after 30 days.
                                                </AlertDialogDescription>
                                            </AlertDialogHeader>
                                            <AlertDialogFooter>
                                                <AlertDialogCancel>
                                                    Cancel
                                                </AlertDialogCancel>
                                                <AlertDialogAction
                                                    onClick={handleDeleteOrganization}
                                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                                    disabled={deleteSubmitting}
                                                >
                                                    {deleteSubmitting ? (
                                                        <span className="inline-flex items-center gap-2">
                                                            <Loader2 className="size-4 animate-spin" />
                                                            Deleting
                                                        </span>
                                                    ) : (
                                                        'Confirm Delete'
                                                    )}
                                                </AlertDialogAction>
                                            </AlertDialogFooter>
                                        </AlertDialogContent>
                                    </AlertDialog>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Users Tab */}
                    <TabsContent value="users" className="mt-0">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Members</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {members.length === 0 ? (
                                    <p className="text-center py-8 text-muted-foreground">
                                        No members yet
                                    </p>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>User</TableHead>
                                                <TableHead>Role</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Last Login</TableHead>
                                            <TableHead className="w-24 text-right">Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {members.map((member) => (
                                                <TableRow key={member.id}>
                                                    <TableCell>
                                                        <div>
                                                            <div className="font-medium">
                                                                {member.display_name}
                                                            </div>
                                                            <div className="text-sm text-muted-foreground">
                                                                {member.email}
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline">{member.role}</Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant={member.is_active ? 'default' : 'secondary'}
                                                        >
                                                            {member.is_active ? 'Active' : 'Inactive'}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {member.last_login_at
                                                            ? formatDistanceToNow(
                                                                  new Date(member.last_login_at),
                                                                  { addSuffix: true }
                                                              )
                                                            : 'Never'}
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="flex items-center justify-end gap-2">
                                                            <AlertDialog>
                                                                <AlertDialogTrigger
                                                                    className={buttonVariants({
                                                                        variant: 'ghost',
                                                                        size: 'sm',
                                                                    })}
                                                                >
                                                                    <ShieldOff className="size-4" />
                                                                </AlertDialogTrigger>
                                                                <AlertDialogContent>
                                                                    <AlertDialogHeader>
                                                                        <AlertDialogTitle>
                                                                            Reset MFA?
                                                                        </AlertDialogTitle>
                                                                        <AlertDialogDescription>
                                                                            This will clear MFA enrollment for{' '}
                                                                            <strong>
                                                                                {member.display_name}
                                                                            </strong>{' '}
                                                                            ({member.email}). They will be
                                                                            required to set up MFA again on
                                                                            next login.
                                                                        </AlertDialogDescription>
                                                                    </AlertDialogHeader>
                                                                    <AlertDialogFooter>
                                                                        <AlertDialogCancel>
                                                                            Cancel
                                                                        </AlertDialogCancel>
                                                                        <AlertDialogAction
                                                                            onClick={() =>
                                                                                handleResetMfa(member)
                                                                            }
                                                                            disabled={
                                                                                mfaResetting === member.id
                                                                            }
                                                                        >
                                                                            {mfaResetting === member.id ? (
                                                                                <span className="inline-flex items-center gap-2">
                                                                                    <Loader2 className="size-4 animate-spin" />
                                                                                    Resetting
                                                                                </span>
                                                                            ) : (
                                                                                'Reset MFA'
                                                                            )}
                                                                        </AlertDialogAction>
                                                                    </AlertDialogFooter>
                                                                </AlertDialogContent>
                                                            </AlertDialog>
                                                            {member.is_active && (
                                                                <AlertDialog>
                                                                    <AlertDialogTrigger
                                                                        className={buttonVariants({
                                                                            variant: 'ghost',
                                                                            size: 'sm',
                                                                            className: 'text-destructive',
                                                                        })}
                                                                    >
                                                                        <UserMinus className="size-4" />
                                                                    </AlertDialogTrigger>
                                                                    <AlertDialogContent>
                                                                        <AlertDialogHeader>
                                                                            <AlertDialogTitle>
                                                                                Deactivate User?
                                                                            </AlertDialogTitle>
                                                                            <AlertDialogDescription>
                                                                                <strong>
                                                                                    {member.display_name}
                                                                                </strong>{' '}
                                                                                ({member.email}) will no longer
                                                                                be able to access {org.name}.
                                                                                This action can be reversed.
                                                                            </AlertDialogDescription>
                                                                        </AlertDialogHeader>
                                                                        <AlertDialogFooter>
                                                                            <AlertDialogCancel>
                                                                                Cancel
                                                                            </AlertDialogCancel>
                                                                            <AlertDialogAction
                                                                                onClick={() =>
                                                                                    handleDeactivateMember(
                                                                                        member.id
                                                                                    )
                                                                                }
                                                                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                                                            >
                                                                                Deactivate
                                                                            </AlertDialogAction>
                                                                        </AlertDialogFooter>
                                                                    </AlertDialogContent>
                                                                </AlertDialog>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Invites Tab */}
                    <TabsContent value="invites" className="mt-0">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle className="text-lg">Invitations</CardTitle>
                                <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
                                    <DialogTrigger
                                        className={buttonVariants({ size: 'sm' })}
                                    >
                                        <Plus className="mr-2 size-4" />
                                        Invite User
                                    </DialogTrigger>
                                    <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Invite user</DialogTitle>
                                    <DialogDescription>
                                        Send an invitation to join {org.name}.
                                        <button
                                            type="button"
                                            className="ml-2 text-xs text-teal-600 hover:underline"
                                            onClick={() => {
                                                setInviteOpen(false);
                                                setActiveTab('templates');
                                            }}
                                        >
                                            Edit invite template
                                        </button>
                                    </DialogDescription>
                                </DialogHeader>
                                        <div className="space-y-4">
                                            <div className="space-y-2">
                                                <Label htmlFor="invite-email">Email</Label>
                                                <Input
                                                    id="invite-email"
                                                    type="email"
                                                    value={inviteForm.email}
                                                    onChange={(e) =>
                                                        setInviteForm((prev) => ({
                                                            ...prev,
                                                            email: e.target.value,
                                                        }))
                                                    }
                                                    placeholder="user@agency.com"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label htmlFor="invite-role">Role</Label>
                                                <Select
                                                    value={inviteForm.role}
                                                    onValueChange={(value) => {
                                                        if (value) {
                                                            setInviteForm((prev) => ({
                                                                ...prev,
                                                                role: value as InviteRole,
                                                            }));
                                                        }
                                                    }}
                                                >
                                                    <SelectTrigger id="invite-role">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {INVITE_ROLE_OPTIONS.map((roleOption) => (
                                                            <SelectItem key={roleOption} value={roleOption}>
                                                                {INVITE_ROLE_LABELS[roleOption]}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            {inviteError && (
                                                <p className="text-sm text-destructive">
                                                    {inviteError}
                                                </p>
                                            )}
                                        </div>
                                        <DialogFooter>
                                            <Button
                                                variant="outline"
                                                onClick={() => setInviteOpen(false)}
                                                disabled={inviteSubmitting}
                                            >
                                                Cancel
                                            </Button>
                                            <Button
                                                onClick={handleCreateInvite}
                                                disabled={inviteSubmitting}
                                            >
                                                {inviteSubmitting ? 'Sending...' : 'Send invite'}
                                            </Button>
                                        </DialogFooter>
                                    </DialogContent>
                                </Dialog>
                            </CardHeader>
                            <CardContent>
                                <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-600 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-300">
                                    <div className="flex flex-col gap-1">
                                        <span>
                                            Invites use the <span className="font-mono">org_invite</span> template.
                                        </span>
                                        {platformEmailLoading ? (
                                            <span className="text-xs text-muted-foreground">
                                                Loading sender status...
                                            </span>
                                        ) : platformEmailStatus?.configured ? (
                                            <span className="text-xs text-muted-foreground">
                                                Platform sender configured (Resend)
                                            </span>
                                        ) : (
                                            <span className="text-xs text-yellow-700 dark:text-yellow-400">
                                                Platform sender not configured — invite emails may fail.
                                            </span>
                                        )}
                                    </div>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setActiveTab('templates')}
                                    >
                                        Manage template
                                    </Button>
                                </div>
                                {invites.length === 0 ? (
                                    <p className="text-center py-8 text-muted-foreground">
                                        No invites yet
                                    </p>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Email</TableHead>
                                                <TableHead>Role</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead>Opened</TableHead>
                                                <TableHead>Clicked</TableHead>
                                                <TableHead>Created</TableHead>
                                                <TableHead className="w-10"></TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {invites.map((invite) => (
                                                <TableRow key={invite.id}>
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            <Mail className="size-4 text-muted-foreground" />
                                                            {invite.email}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline">{invite.role}</Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant="outline"
                                                            className={
                                                                INVITE_STATUS_VARIANTS[invite.status]
                                                            }
                                                        >
                                                            {invite.status}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {invite.open_count && invite.open_count > 0 ? (
                                                            <div className="flex flex-col">
                                                                <span>{invite.open_count} open{invite.open_count === 1 ? '' : 's'}</span>
                                                                {invite.opened_at ? (
                                                                    <span className="text-xs">
                                                                        {formatDistanceToNow(
                                                                            new Date(invite.opened_at),
                                                                            { addSuffix: true }
                                                                        )}
                                                                    </span>
                                                                ) : null}
                                                            </div>
                                                        ) : (
                                                            '-'
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {invite.click_count && invite.click_count > 0 ? (
                                                            <div className="flex flex-col">
                                                                <span>{invite.click_count} click{invite.click_count === 1 ? '' : 's'}</span>
                                                                {invite.clicked_at ? (
                                                                    <span className="text-xs">
                                                                        {formatDistanceToNow(
                                                                            new Date(invite.clicked_at),
                                                                            { addSuffix: true }
                                                                        )}
                                                                    </span>
                                                                ) : null}
                                                            </div>
                                                        ) : (
                                                            '-'
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {formatDistanceToNow(
                                                            new Date(invite.created_at),
                                                            { addSuffix: true }
                                                        )}
                                                    </TableCell>
                                                    <TableCell>
                                                        {invite.status === 'pending' && (
                                                            <AlertDialog>
                                                                <AlertDialogTrigger
                                                                    className={buttonVariants({
                                                                        variant: 'ghost',
                                                                        size: 'sm',
                                                                        className: 'text-destructive',
                                                                    })}
                                                                >
                                                                    <Ban className="size-4" />
                                                                </AlertDialogTrigger>
                                                                <AlertDialogContent>
                                                                    <AlertDialogHeader>
                                                                        <AlertDialogTitle>
                                                                            Revoke Invite?
                                                                        </AlertDialogTitle>
                                                                        <AlertDialogDescription>
                                                                            The invite to{' '}
                                                                            <strong>{invite.email}</strong>{' '}
                                                                            will be invalidated.
                                                                        </AlertDialogDescription>
                                                                    </AlertDialogHeader>
                                                                    <AlertDialogFooter>
                                                                        <AlertDialogCancel>
                                                                            Cancel
                                                                        </AlertDialogCancel>
                                                                        <AlertDialogAction
                                                                            onClick={() =>
                                                                                handleRevokeInvite(invite.id)
                                                                            }
                                                                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                                                        >
                                                                            Revoke
                                                                        </AlertDialogAction>
                                                                    </AlertDialogFooter>
                                                                </AlertDialogContent>
                                                            </AlertDialog>
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Subscription Tab */}
                    <TabsContent value="subscription" className="mt-0 space-y-6">
                        {/* Warning Banner */}
                        <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 p-4">
                            <div className="flex items-start gap-3">
                                <AlertTriangle className="size-5 text-amber-600 mt-0.5" />
                                <div>
                                    <p className="font-medium text-amber-800 dark:text-amber-200">
                                        Billing Not Enforced
                                    </p>
                                    <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                                        Billing is managed offline. No automated charges are processed.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {subscription && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg">Subscription Details</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="grid gap-4 md:grid-cols-3">
                                        <div>
                                            <Label className="text-muted-foreground">Plan</Label>
                                            <div className="mt-1">
                                                <Badge
                                                    className={
                                                        PLAN_BADGE_VARIANTS[subscription.plan_key]
                                                    }
                                                >
                                                    {subscription.plan_key}
                                                </Badge>
                                            </div>
                                        </div>
                                        <div>
                                            <Label className="text-muted-foreground">Status</Label>
                                            <div className="mt-1">
                                                <Badge
                                                    className={
                                                        STATUS_BADGE_VARIANTS[subscription.status]
                                                    }
                                                >
                                                    {subscription.status}
                                                </Badge>
                                            </div>
                                        </div>
                                        <div>
                                            <Label className="text-muted-foreground">Auto-Renew</Label>
                                            <div className="mt-1">
                                                <Switch
                                                    checked={subscription.auto_renew}
                                                    onCheckedChange={handleToggleAutoRenew}
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    <div className="grid gap-4 md:grid-cols-2">
                                        <div>
                                            <Label className="text-muted-foreground">
                                                Current Period End
                                            </Label>
                                            <p className="mt-1 font-medium">
                                                {format(
                                                    new Date(subscription.current_period_end),
                                                    'MMMM d, yyyy'
                                                )}
                                            </p>
                                        </div>
                                        {subscription.trial_end && (
                                            <div>
                                                <Label className="text-muted-foreground">
                                                    Trial End
                                                </Label>
                                                <p className="mt-1 font-medium">
                                                    {format(
                                                        new Date(subscription.trial_end),
                                                        'MMMM d, yyyy'
                                                    )}
                                                </p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Notes */}
                                    <div>
                                        <Label className="text-muted-foreground">Notes</Label>
                                        <Textarea
                                            className="mt-1"
                                            value={notesDraft}
                                            onChange={(event) => setNotesDraft(event.target.value)}
                                            placeholder="Internal notes about this subscription..."
                                        />
                                    </div>

                                    {/* Actions */}
                                    <div className="flex gap-3 pt-4 border-t">
                                        <Button variant="outline" onClick={handleExtendSubscription}>
                                            <CalendarPlus className="mr-2 size-4" />
                                            Extend 30 Days
                                        </Button>
                                        <Button
                                            onClick={handleSaveNotes}
                                            disabled={!notesDirty || notesSaving}
                                        >
                                            {notesSaving ? 'Saving...' : 'Save Notes'}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* Alerts Tab */}
                    <TabsContent value="alerts" className="mt-0">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle className="text-lg">Organization Alerts</CardTitle>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={fetchOrgAlerts}
                                    disabled={alertsLoading}
                                >
                                    {alertsLoading ? 'Refreshing...' : 'Refresh'}
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {alertsLoading ? (
                                    <div className="flex items-center justify-center py-10">
                                        <Loader2 className="size-6 animate-spin text-muted-foreground" />
                                    </div>
                                ) : orgAlerts.length === 0 ? (
                                    <div className="text-center py-10">
                                        <AlertTriangle className="size-10 mx-auto mb-3 text-muted-foreground/50" />
                                        <p className="text-muted-foreground">
                                            No alerts for this organization
                                        </p>
                                    </div>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Alert</TableHead>
                                                <TableHead>Severity</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead>Last Seen</TableHead>
                                                <TableHead className="w-32"></TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {orgAlerts.map((alert) => (
                                                <TableRow key={alert.id}>
                                                    <TableCell>
                                                        <div>
                                                            <div className="font-medium">
                                                                {alert.title}
                                                            </div>
                                                            <div className="text-sm text-muted-foreground">
                                                                {alert.alert_type}
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant="outline"
                                                            className={
                                                                ALERT_SEVERITY_BADGES[alert.severity]
                                                            }
                                                        >
                                                            {alert.severity}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant="outline"
                                                            className={
                                                                ALERT_STATUS_BADGES[alert.status]
                                                            }
                                                        >
                                                            {alert.status}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {formatDistanceToNow(
                                                            new Date(alert.last_seen_at),
                                                            { addSuffix: true }
                                                        )}
                                                    </TableCell>
                                                    <TableCell>
                                                        {alert.status !== 'resolved' && (
                                                            <div className="flex items-center gap-2">
                                                                {alert.status === 'open' && (
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() =>
                                                                            handleAcknowledgeAlert(
                                                                                alert.id
                                                                            )
                                                                        }
                                                                        disabled={
                                                                            alertsUpdating === alert.id
                                                                        }
                                                                    >
                                                                        Acknowledge
                                                                    </Button>
                                                                )}
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    onClick={() =>
                                                                        handleResolveAlert(alert.id)
                                                                    }
                                                                    disabled={
                                                                        alertsUpdating === alert.id
                                                                    }
                                                                >
                                                                    Resolve
                                                                </Button>
                                                            </div>
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Templates Tab */}
                    <TabsContent value="templates" className="mt-0">
                        <div className="grid gap-6 lg:grid-cols-2">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg flex items-center justify-between">
                                        Invite Email Template
                                        <Badge variant="outline" className="font-mono text-xs">
                                            org_invite
                                        </Badge>
                                    </CardTitle>
                                    <CardDescription>
                                        Used for user invites to this agency. Sent via the platform sender (Resend).
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-5">
                                    {platformEmailLoading ? (
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <Loader2 className="size-4 animate-spin" />
                                            Loading email sender status...
                                        </div>
                                    ) : platformEmailStatus?.configured ? (
                                        <div className="rounded-md border bg-stone-50 dark:bg-stone-900 p-3 text-sm">
                                            <div className="flex items-center justify-between">
                                                <span className="text-muted-foreground">
                                                    Sender configured
                                                </span>
                                                <Badge variant="secondary">Resend</Badge>
                                            </div>
                                            <div className="mt-1 text-xs text-muted-foreground">
                                                From: managed per-template
                                                {platformEmailStatus.from_email ? (
                                                    <span className="ml-1 font-mono">
                                                        (fallback: {platformEmailStatus.from_email})
                                                    </span>
                                                ) : null}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">
                                            Platform sender is not configured. Set PLATFORM_RESEND_API_KEY to
                                            enable platform/system emails via Resend.
                                        </div>
                                    )}

                                    {inviteTemplateLoading ? (
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <Loader2 className="size-4 animate-spin" />
                                            Loading template...
                                        </div>
                                    ) : (
                                        <>
                                            <div className="space-y-2">
                                                <Label>From (required for Resend)</Label>
                                                <Input
                                                    value={templateFromEmail}
                                                    onChange={(e) => setTemplateFromEmail(e.target.value)}
                                                    placeholder="Invites <invites@surrogacyforce.com>"
                                                />
                                                <p className="text-xs text-muted-foreground">
                                                    Choose the sender for this template. You can use different
                                                    senders per template without Terraform changes (must be on a
                                                    verified domain in Resend).
                                                </p>
                                            </div>

                                            <div className="space-y-2">
                                                <Label>Subject</Label>
                                                <Input
                                                    value={templateSubject}
                                                    onChange={(e) => setTemplateSubject(e.target.value)}
                                                    placeholder="You're invited to join {{org_name}}"
                                                />
                                                <p className="text-xs text-muted-foreground">
                                                    Variables:{' '}
                                                    <span className="font-mono">{'{{org_name}}'}</span>
                                                </p>
                                            </div>

                                            <div className="space-y-2">
                                                <div className="flex items-center justify-between">
                                                    <Label>Email Body (HTML)</Label>
                                                    <Badge variant="outline" className="text-xs">
                                                        <Code className="size-3 mr-1" />
                                                        Variables
                                                    </Badge>
                                                </div>
                                                <RichTextEditor
                                                    content={templateBody}
                                                    onChange={(html) => setTemplateBody(html)}
                                                    placeholder="Write your invite email content..."
                                                    minHeight="220px"
                                                    maxHeight="420px"
                                                />
                                                <p className="text-xs text-muted-foreground">
                                                    Available variables:{' '}
                                                    <span className="font-mono">{'{{invite_url}}'}</span>,{' '}
                                                    <span className="font-mono">{'{{role_title}}'}</span>,{' '}
                                                    <span className="font-mono">{'{{inviter_text}}'}</span>,{' '}
                                                    <span className="font-mono">{'{{expires_block}}'}</span>
                                                </p>
                                            </div>

                                            <div className="flex items-center justify-between rounded-md border p-3">
                                                <div>
                                                    <div className="font-medium">Template active</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        If disabled, invites use the default built-in template.
                                                    </div>
                                                </div>
                                                <Switch
                                                    checked={templateActive}
                                                    onCheckedChange={setTemplateActive}
                                                />
                                            </div>

                                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                                                <span>
                                                    Version:{' '}
                                                    <span className="font-mono">
                                                        {templateVersion ?? inviteTemplate?.current_version ?? '-'}
                                                    </span>
                                                </span>
                                                <span>
                                                    Updated:{' '}
                                                    {inviteTemplate?.updated_at
                                                        ? format(new Date(inviteTemplate.updated_at), 'MMM d, yyyy h:mm a')
                                                        : '-'}
                                                </span>
                                            </div>

                                            <div className="flex gap-2">
                                                <Button
                                                    onClick={handleSaveInviteTemplate}
                                                    disabled={inviteTemplateSaving}
                                                >
                                                    {inviteTemplateSaving && (
                                                        <Loader2 className="mr-2 size-4 animate-spin" />
                                                    )}
                                                    Save Template
                                                </Button>
                                            </div>

                                            <div className="rounded-md border p-4 space-y-3">
                                                <div className="font-medium">Send Test Email</div>
                                                <div className="grid gap-2">
                                                    <Label className="text-xs">To</Label>
                                                    <Input
                                                        value={testEmail}
                                                        onChange={(e) => setTestEmail(e.target.value)}
                                                        placeholder="name@example.com"
                                                    />
                                                </div>
                                                <Button
                                                    variant="secondary"
                                                    onClick={handleSendTestInviteEmail}
                                                    disabled={
                                                        !platformEmailStatus?.configured ||
                                                        testSending ||
                                                        !(
                                                            templateFromEmail.trim() ||
                                                            platformEmailStatus?.from_email
                                                        )
                                                    }
                                                >
                                                    {testSending && (
                                                        <Loader2 className="mr-2 size-4 animate-spin" />
                                                    )}
                                                    Send Test
                                                </Button>
                                                {!platformEmailStatus?.configured && (
                                                    <p className="text-xs text-muted-foreground">
                                                        Configure platform email sender to enable test sends.
                                                    </p>
                                                )}
                                                {platformEmailStatus?.configured &&
                                                    !templateFromEmail.trim() &&
                                                    !platformEmailStatus?.from_email && (
                                                        <p className="text-xs text-muted-foreground">
                                                            Set a From address above to enable test sends.
                                                        </p>
                                                    )}
                                            </div>
                                        </>
                                    )}
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg">Preview</CardTitle>
                                    <CardDescription>
                                        Sample rendering with mock values.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="rounded-lg border bg-white overflow-hidden">
                                        <div className="border-b bg-muted/30 px-4 py-3 text-sm space-y-2">
                                            <div className="flex items-center gap-2">
                                                <span className="w-16 text-muted-foreground font-medium">From:</span>
                                                <span className="font-mono text-xs">
                                                    {templateFromEmail.trim() ||
                                                        platformEmailStatus?.from_email ||
                                                        "you@company.com"}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="w-16 text-muted-foreground font-medium">To:</span>
                                                <span className="font-mono text-xs">person@example.com</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="w-16 text-muted-foreground font-medium">Subject:</span>
                                                <span className="font-medium">{previewSubject}</span>
                                            </div>
                                        </div>
                                        <div className="p-4">
                                            <div
                                                className="prose prose-sm max-w-none [&_p]:whitespace-pre-wrap"
                                                dangerouslySetInnerHTML={{ __html: previewBody }}
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    {/* Audit Log Tab */}
                    <TabsContent value="audit" className="mt-0">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Admin Action Log</CardTitle>
                                <CardDescription>
                                    Platform admin actions related to this organization
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {actionLogs.length === 0 ? (
                                    <p className="text-center py-8 text-muted-foreground">
                                        No admin actions recorded
                                    </p>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Action</TableHead>
                                                <TableHead>Actor</TableHead>
                                                <TableHead>Details</TableHead>
                                                <TableHead>Time</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {actionLogs.map((log) => (
                                                <TableRow key={log.id}>
                                                    <TableCell className="font-mono text-sm">
                                                        {log.action}
                                                    </TableCell>
                                                    <TableCell className="text-sm">
                                                        {log.actor_email || 'System'}
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                                                        {log.metadata
                                                            ? JSON.stringify(log.metadata)
                                                            : '-'}
                                                    </TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {formatDistanceToNow(
                                                            new Date(log.created_at),
                                                            { addSuffix: true }
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
}
