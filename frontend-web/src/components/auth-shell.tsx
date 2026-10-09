import Link from "next/link";
import type { ComponentType, ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { AbasAuth, type AbaAuth } from "@/components/abas-auth";

/** Casca das telas de entrar/criar conta: formulário à esquerda, painel de destaques à direita. */
export function AuthShell({
  abas,
  eyebrow,
  titulo,
  destaques,
  nota,
  rodape,
  children,
}: {
  abas: AbaAuth[];
  eyebrow: string;
  titulo: string;
  destaques: { icone: ComponentType<{ size?: number }>; texto: string }[];
  nota: ReactNode;
  rodape: string;
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <div className="flex flex-col">
        <header className="flex items-center justify-between px-6 py-5 sm:px-10">
          <Logo />
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-muted transition hover:text-foreground sm:inline-flex"
            >
              <ArrowLeft size={15} /> Voltar ao site
            </Link>
            <ThemeToggle />
          </div>
        </header>

        <main className="flex flex-1 items-center justify-center px-5 pb-16 pt-4">
          <div className="surgir w-full max-w-[400px]">
            <AbasAuth abas={abas} />
            {children}
          </div>
        </main>

        <footer className="px-6 pb-6 text-center text-xs text-muted sm:px-10">{rodape}</footer>
      </div>

      <aside className="relative hidden overflow-hidden bg-petroleo-escuro p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="fundo-pontilhado absolute inset-0 opacity-40 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-primary/30 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-accent/15 blur-3xl" />

        <div className="relative">
          <p className="text-sm font-semibold uppercase tracking-wider text-primary">{eyebrow}</p>
          <h2 className="mt-4 max-w-md font-heading text-4xl font-extrabold leading-tight tracking-tight">{titulo}</h2>
          <ul className="mt-10 flex flex-col gap-5">
            {destaques.map((d) => (
              <li key={d.texto} className="flex items-center gap-3.5 text-[15px] text-white/85">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <d.icone size={19} />
                </span>
                {d.texto}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative max-w-md rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur">{nota}</div>
      </aside>
    </div>
  );
}
