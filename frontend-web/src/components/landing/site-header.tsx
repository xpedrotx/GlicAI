"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { LINK_ASSINAR } from "@/lib/site";

const LINKS = [
  { href: "#como-funciona", rotulo: "Como funciona" },
  { href: "#recursos", rotulo: "Recursos" },
  { href: "#seguranca", rotulo: "Segurança" },
  { href: "#duvidas", rotulo: "Dúvidas" },
];

export function SiteHeader() {
  const [aberto, setAberto] = useState(false);
  const [rolou, setRolou] = useState(false);

  useEffect(() => {
    const aoRolar = () => setRolou(window.scrollY > 8);
    aoRolar();
    window.addEventListener("scroll", aoRolar, { passive: true });
    return () => window.removeEventListener("scroll", aoRolar);
  }, []);

  return (
    <header
      className={`sticky top-0 z-40 transition-colors ${
        rolou || aberto ? "border-b border-border bg-background/85 backdrop-blur-lg" : "border-b border-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-muted transition hover:text-foreground"
            >
              {l.rotulo}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="/login"
            className="hidden rounded-xl px-3.5 py-2 text-sm font-semibold text-foreground transition hover:text-primary sm:inline-flex"
          >
            Entrar
          </Link>
          <a
            href={LINK_ASSINAR}
            className="hidden rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm shadow-primary/30 transition hover:brightness-105 sm:inline-flex"
          >
            Quero assinar
          </a>
          <button
            type="button"
            onClick={() => setAberto(!aberto)}
            aria-label={aberto ? "Fechar menu" : "Abrir menu"}
            aria-expanded={aberto}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border md:hidden"
          >
            {aberto ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {aberto && (
        <nav className="flex flex-col gap-1 border-t border-border px-5 py-4 md:hidden">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setAberto(false)}
              className="rounded-lg px-3 py-2.5 text-[15px] font-medium text-foreground/80"
            >
              {l.rotulo}
            </a>
          ))}
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Link
              href="/login"
              className="rounded-xl border border-border px-4 py-2.5 text-center text-sm font-semibold"
            >
              Entrar
            </Link>
            <a
              href={LINK_ASSINAR}
              onClick={() => setAberto(false)}
              className="rounded-xl bg-primary px-4 py-2.5 text-center text-sm font-semibold text-primary-foreground"
            >
              Quero assinar
            </a>
          </div>
        </nav>
      )}
    </header>
  );
}
