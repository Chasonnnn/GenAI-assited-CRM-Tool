export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 border-r p-4">Sidebar</aside>
      <div className="flex-1">
        <header className="border-b p-4">Topbar</header>
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}