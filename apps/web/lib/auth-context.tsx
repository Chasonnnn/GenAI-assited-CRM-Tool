'use client';

import { createContext, use, useEffect, useState, type ReactNode } from 'react';
import api from '@/lib/api';

// Interface matches backend MeResponse schema
export interface User {
    user_id: string;
    email: string;
    display_name: string;
    avatar_url?: string;
    phone?: string;
    title?: string;
    org_id: string;
    org_name: string;
    org_display_name: string;
    org_slug: string;
    org_timezone: string;
    org_portal_base_url: string;
    role: string;
    ai_enabled: boolean;
    mfa_enabled: boolean;
    mfa_required: boolean;
    mfa_verified: boolean;
    profile_complete: boolean;
}

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    error: Error | null;
    refetch: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    const fetchUser = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.get<User>('/auth/me');
            setUser(data);
        } catch (err) {
            setUser(null);
            if (err instanceof Error) {
                // Don't treat 401 as error - just means not logged in
                if ('status' in err && (err as { status: number }).status === 401) {
                    setError(null);
                } else {
                    setError(err);
                }
            }
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchUser();
    }, []);

    return (
        <AuthContext.Provider value={{ user, isLoading, error, refetch: fetchUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = use(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

// Hook for protected pages
export function useRequireAuth() {
    const { user, isLoading } = useAuth();

    useEffect(() => {
        if (!isLoading && !user) {
            window.location.href = '/login';
        }
        if (
            !isLoading &&
            user &&
            user.mfa_required &&
            !user.mfa_verified
        ) {
            const hasOpsCookie = document.cookie
                .split(';')
                .some((c) => c.trim().startsWith('auth_return_to=ops'));
            const isOpsRoute =
                window.location.pathname.startsWith('/ops') ||
                window.location.hostname.startsWith('ops.');
            const url = hasOpsCookie || isOpsRoute ? '/mfa?return_to=ops' : '/mfa';
            window.location.href = url;
        }
    }, [user, isLoading]);

    return { user, isLoading };
}
