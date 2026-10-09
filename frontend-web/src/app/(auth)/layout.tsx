import Link from "next/link";
import { ArrowLeft, BellRing, Calculator, ChartLine } from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { AbasAuth } from "@/components/abas-auth";

const DESTAQUES = [
  { icone: ChartLine, texto: "Tendência, tempo no alvo e estimativa de HbA1c" },
  { icone: Calculator, texto: "Seu perfil de dose sempre à mão para ajustar" },
  { icone: BellRing, texto: "Cuidadores e estoque de insumos num só lugar" },
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
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
            <AbasAuth />
            {children}
          </div>
        </main>

        <footer className="px-6 pb-6 text-center text-xs text-muted sm:px-10">
          O GlicAI não substitui a orientação da sua equipe de saúde.
        </footer>
      </div>

      <aside className="relative hidden overflow-hidden bg-petroleo-escuro p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="fundo-pontilhado absolute inset-0 opacity-40 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-primary/30 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-accent/15 blur-3xl" />

        <div className="relative">
          <p className="text-sm font-semibold uppercase tracking-wider text-primary">Painel GlicAI</p>
          <h2 className="mt-4 max-w-md font-heading text-4xl font-extrabold leading-tight tracking-tight">
            Tudo o que você conta no WhatsApp, organizado aqui.
          </h2>
          <ul className="mt-10 flex flex-col gap-5">
            {DESTAQUES.map((d) => (
              <li key={d.texto} className="flex items-center gap-3.5 text-[15px] text-white/85">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <d.icone size={19} />
                </span>
                {d.texto}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative max-w-md rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur">
          <p className="text-[15px] leading-relaxed text-white/85">
            “Mande <span className="font-semibold text-white">criar senha</span> para o GlicAI no WhatsApp, receba um
            código de 6 dígitos e crie sua senha na aba <span className="font-semibold text-white">Primeiro acesso</span>
            .”
          </p>
          <p className="mt-3 text-xs font-medium text-white/50">Como liberar seu acesso</p>
        </div>
      </aside>
    </div>
  );
}
