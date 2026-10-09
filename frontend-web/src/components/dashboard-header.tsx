"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChartColumn, LayoutDashboard, LogOut, UserRound, Users } from "lucide-react";
import { useUsuario } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Logo } from "./logo";
import { ThemeToggle } from "./theme-toggle";

const NAV = [
  { href: "/dashboard", rotulo: "Visão geral", icone: LayoutDashboard },
  { href: "/dashboard/relatorios", rotulo: "Relatórios", icone: ChartColumn },
  { href: "/dashboard/cuidadores", rotulo: "Cuidadores e estoque", rotuloCurto: "Cuidadores", icone: Users },
  { href: "/dashboard/perfil", rotulo: "Perfil", icone: UserRound },
];

function useSair() {
  const router = useRouter();
  return async () => {
    await api.logout().catch(() => {});
    router.push("/login");
  };
}

/** Menu lateral fixo no desktop. */
export function DashboardSidebar() {
  const pathname = usePathname();
  const usuario = useUsuario();
  const sair = useSair();
  const nome = usuario?.nome?.trim() || "Paciente";

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-card lg:flex">
      <div className="px-6 py-6">
        <Logo href="/dashboard" />
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {NAV.map((item) => {
          const ativo = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={ativo ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                ativo ? "bg-primary/10 text-primary" : "text-foreground/70 hover:bg-surface hover:text-foreground"
              }`}
            >
              <item.icone size={18} />
              {item.rotulo}
            </Link>
          );
        })}
      </nav>

      <div className="m-3 rounded-2xl border border-border bg-surface p-3">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent text-sm font-bold text-white">
            {nome.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{nome}</p>
            <p className="text-xs text-muted">Conta GlicAI</p>
          </div>
          <ThemeToggle />
        </div>
        <button
          type="button"
          onClick={sair}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-card py-2 text-sm font-medium text-foreground/80 transition hover:border-primary/50 hover:text-primary"
        >
          <LogOut size={16} /> Sair
        </button>
      </div>
    </aside>
  );
}

/** Barra superior + navegação inferior no celular/tablet. */
export function DashboardHeader() {
  const pathname = usePathname();
  const sair = useSair();

  return (
    <>
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/85 px-5 backdrop-blur-lg lg:hidden">
        <Logo href="/dashboard" />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            type="button"
            onClick={sair}
            aria-label="Sair"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-foreground/80 transition hover:border-primary hover:text-primary"
          >
            <LogOut size={17} />
          </button>
        </div>
      </header>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-lg lg:hidden">
        {NAV.map((item) => {
          const ativo = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={ativo ? "page" : undefined}
              className={`flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition ${
                ativo ? "text-primary" : "text-muted"
              }`}
            >
              <item.icone size={20} />
              {item.rotuloCurto ?? item.rotulo}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
