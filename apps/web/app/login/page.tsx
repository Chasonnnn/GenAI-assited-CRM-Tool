import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function LoginPage() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
            <Card className="w-full max-w-md mx-4 shadow-2xl border-0 bg-white/10 backdrop-blur-lg">
                <CardHeader className="text-center pb-2">
                    <div className="mx-auto mb-4 h-16 w-16 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="h-8 w-8 text-white"
                        >
                            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                            <circle cx="9" cy="7" r="4" />
                            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                        </svg>
                    </div>
                    <CardTitle className="text-2xl font-bold text-white">Surrogacy CRM</CardTitle>
                    <CardDescription className="text-slate-300">
                        Sign in to manage your cases
                    </CardDescription>
                </CardHeader>
                <CardContent className="pt-4">
                    <a href={`${API_BASE}/auth/google/login`}>
                        <Button
                            className="w-full h-12 text-base font-medium bg-white text-slate-900 hover:bg-slate-100 transition-all duration-200"
                            size="lg"
                        >
                            <svg className="mr-3 h-5 w-5" viewBox="0 0 24 24">
                                <path
                                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                                    fill="#4285F4"
                                />
                                <path
                                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                    fill="#34A853"
                                />
                                <path
                                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                                    fill="#FBBC05"
                                />
                                <path
                                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                                    fill="#EA4335"
                                />
                            </svg>
                            Continue with Google
                        </Button>
                    </a>

                    <p className="mt-6 text-center text-sm text-slate-400">
                        By signing in, you agree to our Terms of Service and Privacy Policy
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
