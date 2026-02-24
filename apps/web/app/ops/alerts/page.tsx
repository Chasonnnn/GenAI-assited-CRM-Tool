'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from "@/components/app-link";
import { listAlerts, acknowledgeAlert, resolveAlert, type PlatformAlert } from '@/lib/api/platform';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { AlertTriangle, CheckCircle, XCircle, AlertCircle, RefreshCw, Loader2, Building2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';

type SeverityConfig = { icon: React.ElementType; color: string; badge: string };

const DEFAULT_SEVERITY_CONFIG: SeverityConfig = {
    icon: AlertCircle,
    color: 'border-blue-200 bg-blue-50 dark:border-blue-900/50 dark:bg-blue-950/30',
    badge: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
};

const SEVERITY_CONFIG: Record<string, SeverityConfig> = {
    critical: {
        icon: XCircle,
        color: 'border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/30',
        badge: 'bg-red-500/10 text-red-600 border-red-500/20',
    },
    error: {
        icon: AlertTriangle,
        color: 'border-orange-200 bg-orange-50 dark:border-orange-900/50 dark:bg-orange-950/30',
        badge: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
    },
    warn: {
        icon: AlertCircle,
        color: 'border-yellow-200 bg-yellow-50 dark:border-yellow-900/50 dark:bg-yellow-950/30',
        badge: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    },
};

const STATUS_BADGE: Record<string, string> = {
    open: 'bg-red-500/10 text-red-600 border-red-500/20',
    acknowledged: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    resolved: 'bg-green-500/10 text-green-600 border-green-500/20',
    snoozed: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
};

export default function GlobalAlertsPage() {
    const [alerts, setAlerts] = useState<PlatformAlert[]>([]);
    const [total, setTotal] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [severityFilter, setSeverityFilter] = useState<string>('');
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const fetchAlerts = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await listAlerts({
                ...(statusFilter ? { status: statusFilter } : {}),
                ...(severityFilter ? { severity: severityFilter } : {}),
            });
            setAlerts(data.items);
            setTotal(data.total);
        } catch (error) {
            console.error('Failed to fetch alerts:', error);
            toast.error('Failed to load alerts');
        } finally {
            setIsLoading(false);
        }
    }, [statusFilter, severityFilter]);

    useEffect(() => {
        fetchAlerts();
    }, [fetchAlerts]);

    const handleAcknowledge = async (alertId: string) => {
        setActionLoading(alertId);
        try {
            await acknowledgeAlert(alertId);
            setAlerts((prev) =>
                prev.map((a) => (a.id === alertId ? { ...a, status: 'acknowledged' as const } : a))
            );
            toast.success('Alert acknowledged');
        } catch (error) {
            console.error('Failed to acknowledge alert:', error);
            toast.error('Failed to acknowledge alert');
        } finally {
            setActionLoading(null);
        }
    };

    const handleResolve = async (alertId: string) => {
        setActionLoading(alertId);
        try {
            const result = await resolveAlert(alertId);
            setAlerts((prev) =>
                prev.map((a): PlatformAlert =>
                    a.id === alertId
                        ? { ...a, status: 'resolved', resolved_at: result.resolved_at ?? undefined }
                        : a
                )
            );
            toast.success('Alert resolved');
        } catch (error) {
            console.error('Failed to resolve alert:', error);
            toast.error('Failed to resolve alert');
        } finally {
            setActionLoading(null);
        }
    };

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                        Global Alerts
                    </h1>
                    <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
                        {total} total alerts across all agencies
                    </p>
                </div>
                <Button variant="outline" onClick={fetchAlerts} disabled={isLoading}>
                    <RefreshCw className={`mr-2 size-4 ${isLoading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </div>

            {/* Filters */}
            <div className="flex gap-4">
                <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v || '')}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">All statuses</SelectItem>
                        <SelectItem value="open">Open</SelectItem>
                        <SelectItem value="acknowledged">Acknowledged</SelectItem>
                        <SelectItem value="resolved">Resolved</SelectItem>
                        <SelectItem value="snoozed">Snoozed</SelectItem>
                    </SelectContent>
                </Select>

                <Select value={severityFilter} onValueChange={(v) => setSeverityFilter(v || '')}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All severities" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">All severities</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                        <SelectItem value="error">Error</SelectItem>
                        <SelectItem value="warn">Warning</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Alerts List */}
            {isLoading ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="size-8 animate-spin text-muted-foreground" />
                </div>
            ) : alerts.length === 0 ? (
                <div className="text-center py-16 border rounded-lg bg-white dark:bg-stone-900">
                    <CheckCircle className="mx-auto size-12 text-green-500/50 mb-4" />
                    <h3 className="text-lg font-medium text-foreground">No alerts</h3>
                    <p className="text-muted-foreground mt-1">All systems are operating normally</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {alerts.map((alert) => {
                        const config = SEVERITY_CONFIG[alert.severity] ?? DEFAULT_SEVERITY_CONFIG;
                        const Icon = config.icon;

                        return (
                            <div
                                key={alert.id}
                                className={`flex items-start gap-4 rounded-lg border p-4 ${config.color}`}
                            >
                                <Icon className="mt-0.5 size-5 flex-shrink-0" />
                                <div className="flex-1 space-y-2">
                                    <div className="flex items-start justify-between gap-2">
                                        <div>
                                            <p className="font-medium text-stone-900 dark:text-stone-100">
                                                {alert.title}
                                            </p>
                                            <Link
                                                href={`/ops/agencies/${alert.organization_id}`}
                                                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline"
                                            >
                                                <Building2 className="size-3" />
                                                {alert.org_name}
                                            </Link>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className={config.badge}>
                                                {alert.severity}
                                            </Badge>
                                            <Badge variant="outline" className={STATUS_BADGE[alert.status]}>
                                                {alert.status}
                                            </Badge>
                                        </div>
                                    </div>

                                    {alert.message && (
                                        <p className="text-sm text-muted-foreground">{alert.message}</p>
                                    )}

                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                            <span>
                                                Last seen:{' '}
                                                {formatDistanceToNow(new Date(alert.last_seen_at), {
                                                    addSuffix: true,
                                                })}
                                            </span>
                                            {alert.occurrence_count > 1 && (
                                                <span className="font-medium">
                                                    {alert.occurrence_count} occurrences
                                                </span>
                                            )}
                                        </div>

                                        {alert.status !== 'resolved' && (
                                            <div className="flex gap-2">
                                                {alert.status === 'open' && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => handleAcknowledge(alert.id)}
                                                        disabled={actionLoading === alert.id}
                                                    >
                                                        {actionLoading === alert.id ? (
                                                            <Loader2 className="mr-1 size-3 animate-spin" />
                                                        ) : null}
                                                        Acknowledge
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleResolve(alert.id)}
                                                    disabled={actionLoading === alert.id}
                                                >
                                                    {actionLoading === alert.id ? (
                                                        <Loader2 className="mr-1 size-3 animate-spin" />
                                                    ) : null}
                                                    Resolve
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
