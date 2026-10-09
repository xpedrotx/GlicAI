import { MedicoProvider } from "@/lib/medico-context";
import { MedicoHeader, MedicoSidebar } from "@/components/medico-nav";

export default function PainelMedicoLayout({ children }: { children: React.ReactNode }) {
  return (
    <MedicoProvider>
      <div className="flex min-h-screen bg-surface">
        <MedicoSidebar />
        <div className="min-w-0 flex-1">
          <MedicoHeader />
          <main className="mx-auto max-w-6xl px-5 pb-28 pt-8 sm:px-8 lg:pb-12 lg:pt-10">{children}</main>
        </div>
      </div>
    </MedicoProvider>
  );
}
