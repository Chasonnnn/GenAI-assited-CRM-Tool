import { AuthProvider } from "@/lib/auth-context"

export default function MfaLayout({ children }: { children: React.ReactNode }) {
    return <AuthProvider>{children}</AuthProvider>
}
