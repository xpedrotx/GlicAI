import { BellRing, Calculator, ChartLine } from "lucide-react";
import { AuthShell } from "@/components/auth-shell";

const ABAS = [
  { href: "/login", rotulo: "Entrar" },
  { href: "/criar-senha", rotulo: "Primeiro acesso" },
];

const DESTAQUES = [
  { icone: ChartLine, texto: "Tendência, tempo no alvo e estimativa de HbA1c" },
  { icone: Calculator, texto: "Seu perfil de dose sempre à mão para ajustar" },
  { icone: BellRing, texto: "Cuidadores e estoque de insumos num só lugar" },
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthShell
      abas={ABAS}
      eyebrow="Painel GlicAI"
      titulo="Tudo o que você conta no WhatsApp, organizado aqui."
      destaques={DESTAQUES}
      rodape="O GlicAI não substitui a orientação da sua equipe de saúde."
      nota={
        <>
          <p className="text-[15px] leading-relaxed text-white/85">
            “Mande <span className="font-semibold text-white">criar senha</span> para o GlicAI no WhatsApp, receba um
            código de 6 dígitos e crie sua senha na aba <span className="font-semibold text-white">Primeiro acesso</span>
            .”
          </p>
          <p className="mt-3 text-xs font-medium text-white/50">Como liberar seu acesso</p>
        </>
      }
    >
      {children}
    </AuthShell>
  );
}
