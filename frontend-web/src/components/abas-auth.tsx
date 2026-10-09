"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type AbaAuth = { href: string; rotulo: string };

export function AbasAuth({ abas }: { abas: AbaAuth[] }) {
  const pathname = usePathname();
  return (
    <nav className="mb-8 grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface p-1" aria-label="Acesso">
      {abas.map((a) => {
        const ativa = pathname === a.href;
        return (
          <Link
            key={a.href}
            href={a.href}
            aria-current={ativa ? "page" : undefined}
            className={`rounded-lg py-2 text-center text-sm font-semibold transition ${
              ativa ? "bg-card text-foreground shadow-sm" : "text-muted hover:text-foreground"
            }`}
          >
            {a.rotulo}
          </Link>
        );
      })}
    </nav>
  );
}
