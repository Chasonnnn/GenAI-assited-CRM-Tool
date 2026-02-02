import AppShellClient from "@/components/app-shell-client"
import { AuthProvider } from "@/lib/auth-context"

export const dynamic = "force-dynamic"
export const revalidate = 0

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <AppShellClient>{children}</AppShellClient>
    </AuthProvider>
  )
}
