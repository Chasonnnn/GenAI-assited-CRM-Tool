'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import api from '@/lib/api';

interface User {
    id: string;
    email: string;
    display_name: string;
    organization: {
        id: string;
        name: string;
        slug: string;
    };
    role: string;
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
    const context = useContext(AuthContext);
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
    }, [user, isLoading]);

    return { user, isLoading };
}
