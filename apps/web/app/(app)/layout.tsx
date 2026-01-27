import AppShellClient from "@/components/app-shell-client"

export const dynamic = "force-dynamic"
export const revalidate = 0

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShellClient>{children}</AppShellClient>
}
