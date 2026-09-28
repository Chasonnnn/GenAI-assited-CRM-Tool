'use client';

import { type ElementType } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from "@/components/app-link";
import { buttonVariants } from '@/components/ui/button-variants';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Building2, Users, AlertTriangle, Plus, Loader2, ChevronRight, CheckCircle } from 'lucide-react';
import { getPlatformStats, listAlerts } from '@/lib/api/platform';
import { PageHeader } from '@/components/page-header';
import { EmptyState } from '@/components/empty-state';
import { LoadErrorState } from '@/components/error-state';
import { cn } from '@/lib/utils';
import {
    ALERT_STATUS_BADGES,
    getAlertSeverityLabel,
    getAlertStatusLabel,
} from '@/components/ops/agencies/agency-constants';

function StatCard({
    title,
    value,
    icon: Icon,
    caption,
    variant = 'default',
    href,
}: {
    title: string;
    value: number;
    icon: ElementType;
    caption?: string;
    variant?: 'default' | 'warning';
    href?: string;
}) {
    const isWarning = variant === 'warning' && value > 0;
    const card = (
        <Card
            className={cn(
                'h-full gap-2 transition-colors',
                isWarning && 'border-amber-200 dark:border-amber-900/50',
                href && 'group-hover:border-primary/40 group-hover:bg-muted/30',
            )}
        >
            <CardHeader className="flex flex-row items-center justify-between gap-y-0">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                    {title}
                </CardTitle>
                <Icon
                    className={cn('size-5', isWarning ? 'text-amber-500' : 'text-muted-foreground')}
                    aria-hidden="true"
                />
            </CardHeader>
            <CardContent className="flex items-end justify-between gap-2">
                <div>
                    <div className="text-3xl font-bold text-foreground">{value.toLocaleString()}</div>
                    {caption ? <p className="mt-1 text-xs text-muted-foreground">{caption}</p> : null}
                </div>
                {href ? (
                    <ChevronRight
                        className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                        aria-hidden="true"
                    />
                ) : null}
            </CardContent>
        </Card>
    );

    if (!href) return card;
    return (
        <Link
            href={href}
            className="group block rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
            {card}
        </Link>
    );
}

export default function OpsDashboard() {
    const dashboardQuery = useQuery({
        queryKey: ['platform', 'ops-dashboard'],
        queryFn: async () => {
            const [stats, alerts] = await Promise.all([
                getPlatformStats(),
                listAlerts({ limit: 5, status: 'open' }),
            ]);
            return { stats, recentAlerts: alerts.items };
        },
        retry: false,
        staleTime: 30_000,
    });
    const { stats, recentAlerts } = dashboardQuery.data ?? {
        stats: null,
        recentAlerts: [],
    };

    const header = (
        <PageHeader
            title="Dashboard"
            actions={
                <Link href="/ops/agencies/new" className={buttonVariants()}>
                    <Plus className="size-4" aria-hidden="true" />
                    Create Agency
                </Link>
            }
        />
    );

    if (dashboardQuery.isLoading) {
        return (
            <div>
                {header}
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="size-8 animate-spin text-muted-foreground" aria-label="Loading" />
                </div>
            </div>
        );
    }

    if (dashboardQuery.isError || !stats) {
        return (
            <div>
                {header}
                <div className="p-6">
                    <LoadErrorState
                        title="Couldn't load dashboard"
                        onRetry={() => void dashboardQuery.refetch()}
                        isRetrying={dashboardQuery.isFetching}
                        headingLevel={2}
                    />
                </div>
            </div>
        );
    }

    return (
        <div>
            {header}
            <div className="flex flex-col gap-6 p-6">
            {/* Stats Grid */}
            <div className="grid gap-4 md:grid-cols-3">
                <StatCard
                    title="Agencies"
                    value={stats.agency_count ?? 0}
                    icon={Building2}
                    href="/ops/agencies"
                />
                <StatCard
                    title="Active Users"
                    value={stats.active_user_count ?? 0}
                    icon={Users}
                    caption="Last 30 days"
                />
                <StatCard
                    title="Open Alerts"
                    value={stats.open_alerts ?? 0}
                    icon={AlertTriangle}
                    variant={stats.open_alerts > 0 ? 'warning' : 'default'}
                    href="/ops/alerts"
                />
            </div>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-lg">
                        <h2>Recent Alerts</h2>
                    </CardTitle>
                    <Link href="/ops/alerts" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
                        View all
                    </Link>
                </CardHeader>
                <CardContent>
                    {recentAlerts.length === 0 ? (
                        <EmptyState
                            icon={CheckCircle}
                            title="No open alerts"
                            headingLevel={3}
                            className="min-h-0 py-8"
                        />
                    ) : (
                        <div className="space-y-3">
                            {recentAlerts.map((alert) => (
                                <Link
                                    key={alert.id}
                                    href={`/ops/agencies/${alert.organization_id}`}
                                    className="block rounded-md border border-border p-3 hover:bg-muted/50 transition-colors"
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="min-w-0 space-y-1">
                                            <p className="text-sm font-medium text-foreground">
                                                {alert.title}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {alert.org_name} · {getAlertSeverityLabel(alert.severity)}
                                            </p>
                                        </div>
                                        <Badge variant="outline" className={ALERT_STATUS_BADGES[alert.status]}>
                                            {getAlertStatusLabel(alert.status)}
                                        </Badge>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
            </div>
        </div>
    );
}
