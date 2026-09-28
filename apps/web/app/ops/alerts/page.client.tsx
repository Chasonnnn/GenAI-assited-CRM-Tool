'use client';

import { useReducer, type ElementType } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
import { RelativeTime } from '@/components/ui/time-display';
import { AlertTriangle, CheckCircle, XCircle, AlertCircle, RefreshCw, Loader2, Building2, BellIcon } from 'lucide-react';
import { toast } from '@/components/ui/toast';
import { PageHeader } from '@/components/page-header';
import { EmptyState } from '@/components/empty-state';
import { QueryErrorState } from '@/components/error-state';
import { toSelectOptions } from '@/lib/select-labels';
import {
    ALERT_SEVERITY_LABELS,
    ALERT_STATUS_LABELS,
    getAlertSeverityLabel,
    getAlertStatusLabel,
} from '@/components/ops/agencies/agency-constants';

type SeverityConfig = { icon: ElementType; color: string; badge: string };

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

type AlertsState = {
    statusFilter: string
    severityFilter: string
    actionLoading: string | null
}

type AlertsAction =
    | { type: "set-status-filter"; statusFilter: string }
    | { type: "set-severity-filter"; severityFilter: string }
    | { type: "set-action-loading"; alertId: string | null }
    | { type: "clear-filters" }

const INITIAL_ALERTS_STATE: AlertsState = {
    statusFilter: "",
    severityFilter: "",
    actionLoading: null,
}

function alertsReducer(state: AlertsState, action: AlertsAction): AlertsState {
    switch (action.type) {
        case "set-status-filter":
            return { ...state, statusFilter: action.statusFilter }
        case "set-severity-filter":
            return { ...state, severityFilter: action.severityFilter }
        case "set-action-loading":
            return { ...state, actionLoading: action.alertId }
        case "clear-filters":
            return { ...state, statusFilter: "", severityFilter: "" }
    }
}

type AlertsResponse = Awaited<ReturnType<typeof listAlerts>>;

export default function GlobalAlertsPage() {
    const [state, dispatch] = useReducer(alertsReducer, INITIAL_ALERTS_STATE);
    const { statusFilter, severityFilter, actionLoading } = state;
    const queryClient = useQueryClient();
    const alertsQueryKey = [
        'platform',
        'alerts',
        { status: statusFilter || null, severity: severityFilter || null },
    ] as const;
    const alertsQuery = useQuery({
        queryKey: alertsQueryKey,
        queryFn: () =>
            listAlerts({
                ...(statusFilter ? { status: statusFilter } : {}),
                ...(severityFilter ? { severity: severityFilter } : {}),
            }),
        retry: false,
        staleTime: 30_000,
    });
    const alerts = alertsQuery.data?.items ?? [];
    const isLoading = alertsQuery.isFetching;
    const hasActiveFilters = statusFilter !== '' || severityFilter !== '';

    const fetchAlerts = () => {
        void alertsQuery.refetch();
    };

    const updateCurrentAlerts = (updateAlert: (alert: PlatformAlert) => PlatformAlert) => {
        queryClient.setQueryData<AlertsResponse>(alertsQueryKey, (current) =>
            current
                ? { ...current, items: current.items.map(updateAlert) }
                : current
        );
    };

    const handleAcknowledge = async (alertId: string) => {
        dispatch({ type: "set-action-loading", alertId });
        const result = await acknowledgeAlert(alertId).then(() => ({
            status: "success" as const,
        })).catch((error: unknown) => ({
            status: "error" as const,
            error,
        }));

        if (result.status === "success") {
            updateCurrentAlerts((alert) =>
                alert.id === alertId ? { ...alert, status: "acknowledged" } : alert
            );
            toast.success('Alert acknowledged');
        } else {
            console.error('Failed to acknowledge alert:', result.error);
            toast.error('Failed to acknowledge alert');
        }
        dispatch({ type: "set-action-loading", alertId: null });
    };

    const handleResolve = async (alertId: string) => {
        dispatch({ type: "set-action-loading", alertId });
        const result = await resolveAlert(alertId).then((alert) => ({
            status: "success" as const,
            resolvedAt: alert.resolved_at ?? undefined,
        })).catch((error: unknown) => ({
            status: "error" as const,
            error,
        }));

        if (result.status === "success") {
            updateCurrentAlerts((alert) =>
                alert.id === alertId
                    ? { ...alert, status: "resolved", resolved_at: result.resolvedAt }
                    : alert
            );
            toast.success('Alert resolved');
        } else {
            console.error('Failed to resolve alert:', result.error);
            toast.error('Failed to resolve alert');
        }
        dispatch({ type: "set-action-loading", alertId: null });
    };

    return (
        <div>
            <PageHeader
                title="Alerts"
                actions={
                    <Button variant="outline" onClick={fetchAlerts} disabled={isLoading}>
                        <RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
                        Refresh
                    </Button>
                }
            />

            <div className="p-6 space-y-6">
            {/* Filters */}
            <div className="flex flex-wrap gap-4">
                <Select
                    value={statusFilter}
                    onValueChange={(v) => dispatch({ type: "set-status-filter", statusFilter: v || "" })}
                >
                    <SelectTrigger className="w-full sm:w-[180px]" aria-label="Filter by status">
                        <SelectValue placeholder="All statuses">{getAlertStatusLabel}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">All statuses</SelectItem>
                        {toSelectOptions(ALERT_STATUS_LABELS).map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                <Select
                    value={severityFilter}
                    onValueChange={(v) => dispatch({ type: "set-severity-filter", severityFilter: v || "" })}
                >
                    <SelectTrigger className="w-full sm:w-[180px]" aria-label="Filter by severity">
                        <SelectValue placeholder="All severities">{getAlertSeverityLabel}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">All severities</SelectItem>
                        {toSelectOptions(ALERT_SEVERITY_LABELS).map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Alerts List */}
            {alertsQuery.isError ? (
                <div className="border rounded-lg bg-card">
                    <QueryErrorState
                        error={alertsQuery.error}
                        onRetry={fetchAlerts}
                        isRetrying={alertsQuery.isFetching}
                        title="Couldn't load alerts"
                        headingLevel={2}
                        className="min-h-0 py-12"
                    />
                </div>
            ) : isLoading ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="size-8 animate-spin text-muted-foreground" />
                </div>
            ) : alerts.length === 0 ? (
                <div className="border rounded-lg bg-card">
                    {hasActiveFilters ? (
                        <EmptyState
                            icon={BellIcon}
                            title="No matching alerts"
                            headingLevel={2}
                            onClearFilters={() => dispatch({ type: "clear-filters" })}
                        />
                    ) : (
                        <EmptyState icon={CheckCircle} title="No alerts" headingLevel={2} />
                    )}
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
                                <Icon className="mt-0.5 size-5 flex-shrink-0" aria-hidden="true" />
                                <div className="min-w-0 flex-1 space-y-2">
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <p className="font-medium text-foreground">
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
                                                {getAlertSeverityLabel(alert.severity)}
                                            </Badge>
                                            <Badge variant="outline" className={STATUS_BADGE[alert.status]}>
                                                {getAlertStatusLabel(alert.status)}
                                            </Badge>
                                        </div>
                                    </div>

                                    {alert.message && (
                                        <p className="text-sm text-muted-foreground">{alert.message}</p>
                                    )}

                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                            <span>
                                                Last seen:{' '}
                                                <RelativeTime value={alert.last_seen_at} />
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
        </div>
    );
}
