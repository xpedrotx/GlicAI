import { Activity, ShieldCheck, Users } from "lucide-react";
import { AuthShell } from "@/components/auth-shell";

const ABAS = [
  { href: "/medico/entrar", rotulo: "Entrar" },
  { href: "/medico/cadastro", rotulo: "Criar conta" },
];

const DESTAQUES = [
  { icone: Users, texto: "Acompanhe seus pacientes num só painel" },
  { icone: Activity, texto: "Glicemias, doses, tempo no alvo e HbA1c estimada" },
  { icone: ShieldCheck, texto: "Acesso liberado pelo próprio paciente, que pode revogar" },
];

export default function AuthMedicoLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthShell
      abas={ABAS}
      eyebrow="Para médicos"
      titulo="Dados reais do dia a dia do seu paciente, antes da consulta."
      destaques={DESTAQUES}
      rodape="O GlicAI é uma ferramenta de apoio e não substitui a avaliação clínica."
      nota={
        <>
          <p className="text-[15px] leading-relaxed text-white/85">
            “Você recebe um <span className="font-semibold text-white">código de vinculação</span>. O paciente digita
            o código e confirma. Só então os dados dele aparecem para você.”
          </p>
          <p className="mt-3 text-xs font-medium text-white/50">Como funciona o acesso</p>
        </>
      }
    >
      {children}
    </AuthShell>
  );
}
