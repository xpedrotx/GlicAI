import { AuthProvider } from "@/lib/auth-context";
import { DashboardHeader, DashboardSidebar } from "@/components/dashboard-header";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="flex min-h-screen bg-surface">
        <DashboardSidebar />
        <div className="min-w-0 flex-1">
          <DashboardHeader />
          <main className="mx-auto max-w-6xl px-5 pb-28 pt-8 sm:px-8 lg:pb-12 lg:pt-10">{children}</main>
        </div>
      </div>
    </AuthProvider>
  );
}
