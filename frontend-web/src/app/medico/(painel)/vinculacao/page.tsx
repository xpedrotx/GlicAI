"use client";

import { useState } from "react";
import { Check, Copy, Eye, EyeOff, MessageCircle, ShieldCheck } from "lucide-react";
import { useMedico } from "@/lib/medico-context";
import { Button, Card, CardTitulo, PageHeader } from "@/components/ui";

export default function VinculacaoPage() {
  const medico = useMedico();
  const [copiado, setCopiado] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(medico.codigo_vinculo);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      /* sem permissão de área de transferência: o código continua visível pra copiar na mão */
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Código de vinculação" descricao="O paciente usa este código para liberar o acompanhamento a você." />

      <Card className="max-w-2xl border-primary/30">
        <p className="text-sm font-medium text-muted">Seu código</p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
          <p className="font-heading text-4xl font-extrabold tracking-[0.12em] text-primary sm:text-5xl">{medico.codigo_vinculo}</p>
          <Button variant="ghost" onClick={copiar}>
            {copiado ? <Check size={16} /> : <Copy size={16} />}
            {copiado ? "Copiado!" : "Copiar código"}
          </Button>
        </div>
        <p className="mt-4 text-sm text-muted">
          Este é o seu código fixo: pode passar para todos os seus pacientes. Ele sozinho não dá acesso a nada, quem
          libera é o paciente.
        </p>
      </Card>

      <Card className="max-w-2xl">
        <CardTitulo icone={<MessageCircle size={18} />} titulo="Como o paciente vincula" descricao="Dois jeitos, o paciente escolhe." />
        <ol className="flex flex-col gap-4 text-[15px]">
          <Passo n={1}>
            <span className="font-semibold">No WhatsApp:</span> manda para o GlicAI{" "}
            <code className="rounded-md bg-surface px-1.5 py-0.5 font-mono text-sm">medico {medico.codigo_vinculo}</code>
          </Passo>
          <Passo n={2}>
            <span className="font-semibold">No painel dele:</span> aba <span className="font-medium">Médicos</span>, digita o
            código e confirma.
          </Passo>
          <Passo n={3}>
            O GlicAI mostra para o paciente o seu nome e CRM ({medico.nome}, CRM {medico.crm}/{medico.uf}) para ele conferir
            antes de confirmar. Depois disso, ele aparece em <span className="font-medium">Pacientes</span>.
          </Passo>
        </ol>
      </Card>

      <Card className="max-w-2xl">
        <CardTitulo icone={<ShieldCheck size={18} />} titulo="Privacidade" />
        <ul className="flex flex-col gap-3 text-sm">
          <li className="flex items-start gap-2.5">
            <Eye size={17} className="mt-0.5 shrink-0 text-verde" />
            <span>
              <span className="font-semibold">Você vê:</span> nome, glicemias, doses de insulina, relatórios e o perfil de dose
              do paciente (meta, limites, fator de sensibilidade, relação insulina:carboidrato e basal).
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <EyeOff size={17} className="mt-0.5 shrink-0 text-vermelho" />
            <span>
              <span className="font-semibold">Você não vê:</span> telefone, CPF nem as conversas do paciente com o GlicAI. E
              não consegue alterar nada.
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <ShieldCheck size={17} className="mt-0.5 shrink-0 text-primary" />
            <span>
              O paciente pode revogar o acesso quando quiser, e você também pode remover um paciente da sua lista. Use os dados
              apenas para o cuidado do paciente, conforme a LGPD e o sigilo médico.
            </span>
          </li>
        </ul>
      </Card>
    </div>
  );
}

function Passo({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">{n}</span>
      <p className="leading-relaxed">{children}</p>
    </li>
  );
}
