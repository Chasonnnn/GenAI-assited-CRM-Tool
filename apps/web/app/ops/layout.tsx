'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from "@/components/app-link";
import { getPlatformMe, getPlatformStats, type PlatformUser } from '@/lib/api/platform';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ShieldCheck, Building2, Bell, LogOut, Loader2, LayoutTemplate } from 'lucide-react';
import api, { ApiError } from '@/lib/api';

function NavLink({
    href,
    exact = false,
    children,
}: {
    href: string;
    exact?: boolean;
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const isActive = exact ? pathname === href : pathname.startsWith(href);

    return (
        <Link
            href={href}
            className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                isActive
                    ? 'bg-teal-600/10 text-teal-600 dark:text-teal-400'
                    : 'text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800 hover:text-stone-900 dark:hover:text-stone-100'
            }`}
        >
            {children}
        </Link>
    );
}

export default function OpsLayout({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<PlatformUser | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [openAlertCount, setOpenAlertCount] = useState(0);
    const router = useRouter();
    const pathname = usePathname();

    // Skip auth check for login page
    const isLoginPage = pathname === '/ops/login';

    useEffect(() => {
        if (isLoginPage) {
            setIsLoading(false);
            return;
        }

        async function checkPlatformAdmin() {
            try {
                const statsPromise = getPlatformStats().catch(() => null);
                const data = await getPlatformMe();
                setUser(data);
                const stats = await statsPromise;
                setOpenAlertCount(stats?.open_alerts ?? 0);
            } catch (error) {
                if (error instanceof ApiError && error.status === 403) {
                    const message = (error.message || '').toLowerCase();
                    if (message.includes('mfa')) {
                        router.replace('/mfa');
                        return;
                    }
                }
                // Not authenticated or not platform admin
                router.replace('/ops/login');
            } finally {
                setIsLoading(false);
            }
        }
        checkPlatformAdmin();
    }, [router, isLoginPage]);

    const handleLogout = async () => {
        try {
            await api.post('/auth/logout');
        } catch {
            // Ignore errors
        }
        window.location.href = '/ops/login';
    };

    // Don't show layout for login page
    if (isLoginPage) {
        return <>{children}</>;
    }

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-stone-50 dark:bg-stone-950">
                <Loader2 className="size-8 animate-spin text-teal-600" />
            </div>
        );
    }

    if (!user) {
        return null;
    }

    return (
        <div className="min-h-screen bg-stone-50 dark:bg-stone-950">
            {/* Top Header */}
            <header className="sticky top-0 z-50 border-b border-stone-200 dark:border-stone-800 bg-white/95 dark:bg-stone-900/95 backdrop-blur">
                <div className="flex h-14 items-center justify-between px-6">
                    <div className="flex items-center gap-6">
                        {/* Logo/Brand */}
                        <Link href="/ops" className="flex items-center gap-2">
                            <div className="size-8 rounded-lg bg-teal-600 flex items-center justify-center">
                                <ShieldCheck className="size-5 text-white" />
                            </div>
                            <span className="font-semibold text-lg text-stone-900 dark:text-stone-100">
                                Ops Console
                            </span>
                        </Link>

                        {/* Nav Links */}
                        <nav className="flex items-center gap-1">
                            <NavLink href="/ops" exact>
                                Dashboard
                            </NavLink>
                            <NavLink href="/ops/agencies">
                                <span className="flex items-center gap-1.5">
                                    <Building2 className="size-4" />
                                    Agencies
                                </span>
                            </NavLink>
                            <NavLink href="/ops/alerts">
                                <span className="flex items-center gap-1.5">
                                    <Bell className="size-4" />
                                    Alerts
                                    {openAlertCount > 0 && (
                                        <Badge
                                            variant="destructive"
                                            className="px-1.5 py-0 text-xs h-5"
                                        >
                                            {openAlertCount}
                                        </Badge>
                                    )}
                                </span>
                            </NavLink>
                            <NavLink href="/ops/templates">
                                <span className="flex items-center gap-1.5">
                                    <LayoutTemplate className="size-4" />
                                    Templates
                                </span>
                            </NavLink>
                        </nav>
                    </div>

                    {/* User Menu */}
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-stone-500 dark:text-stone-400">
                            {user.email}
                        </span>
                        <Button variant="ghost" size="sm" onClick={handleLogout}>
                            <LogOut className="size-4" />
                        </Button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="min-h-[calc(100vh-3.5rem)]">{children}</main>
        </div>
    );
}
