import { AppSidebar } from "@/components/app-sidebar"

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppSidebar>{children}</AppSidebar>;
}