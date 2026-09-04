"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useUsuario } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Logo } from "./logo";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "./ui";

const NAV = [
  { href: "/dashboard", rotulo: "Histórico" },
  { href: "/dashboard/relatorios", rotulo: "Relatórios" },
  { href: "/dashboard/cuidadores", rotulo: "Cuidadores" },
  { href: "/dashboard/perfil", rotulo: "Perfil" },
];

export function DashboardHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const usuario = useUsuario();

  async function sair() {
    await api.logout().catch(() => {});
    router.push("/login");
  }

  return (
    <header className="border-b border-border">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-8">
          <Logo />
          <nav className="hidden gap-1 sm:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  pathname === item.href ? "bg-primary/10 text-primary" : "text-muted hover:text-foreground"
                }`}
              >
                {item.rotulo}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {usuario?.nome && (
            <span className="hidden text-sm text-muted sm:inline">Oi, {usuario.nome.split(" ")[0]}</span>
          )}
          <ThemeToggle />
          <Button variant="ghost" onClick={sair} className="w-auto px-4">
            Sair
          </Button>
        </div>
      </div>
      <nav className="flex gap-1 border-t border-border px-6 py-2 sm:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              pathname === item.href ? "bg-primary/10 text-primary" : "text-muted hover:text-foreground"
            }`}
          >
            {item.rotulo}
          </Link>
        ))}
      </nav>
    </header>
  );
}
