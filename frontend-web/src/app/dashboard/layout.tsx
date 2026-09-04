import { AuthProvider } from "@/lib/auth-context";
import { DashboardHeader } from "@/components/dashboard-header";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="min-h-screen">
        <DashboardHeader />
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
      </div>
    </AuthProvider>
  );
}
