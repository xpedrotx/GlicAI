"use client";

import { useEffect, useState } from "react";
import { Clock, SlidersHorizontal, Syringe, TriangleAlert, UserRound, Utensils } from "lucide-react";
import { api } from "@/lib/api";
import type { PerfilCompleto } from "@/lib/types";
import { Card, CardTitulo, PageHeader, Skeleton, Vazio } from "@/components/ui";
import { EditableField } from "@/components/editable-field";

export default function PerfilPage() {
  const [dados, setDados] = useState<PerfilCompleto | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api
      .perfil()
      .then(setDados)
      .catch(() => setErro("Não consegui carregar seu perfil agora."))
      .finally(() => setCarregando(false));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Perfil e configurações"
        descricao="Os parâmetros que o GlicAI usa para calcular sua dose. Ajuste sempre com orientação médica."
      />

      {carregando && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-[420px]" />
          <Skeleton className="h-[420px]" />
        </div>
      )}

      {erro && (
        <Card>
          <Vazio icone={<TriangleAlert size={20} />} titulo={erro} />
        </Card>
      )}

      {dados && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <Card>
            <CardTitulo icone={<UserRound size={18} />} titulo="Dados gerais" descricao="Clique em Editar para alterar." />
            <div>
              <EditableField
                campo="nome"
                rotulo="Nome"
                valorAtual={dados.nome ?? ""}
                onSalvo={(v) => setDados({ ...dados, nome: v })}
              />
              <EditableField
                campo="meta_glicemia"
                rotulo="Meta"
                valorAtual={String(dados.meta_glicemia)}
                sufixo=" mg/dL"
                onSalvo={(v) => setDados({ ...dados, meta_glicemia: Number(v) })}
              />
              <EditableField
                campo="limite_baixo"
                rotulo="Limite baixo (hipoglicemia)"
                valorAtual={String(dados.limite_baixo)}
                sufixo=" mg/dL"
                onSalvo={(v) => setDados({ ...dados, limite_baixo: Number(v) })}
              />
              <EditableField
                campo="limite_alto"
                rotulo="Limite alto (hiperglicemia)"
                valorAtual={String(dados.limite_alto)}
                sufixo=" mg/dL"
                onSalvo={(v) => setDados({ ...dados, limite_alto: Number(v) })}
              />
              <EditableField
                campo="fator_sensibilidade"
                rotulo="Fator de sensibilidade"
                valorAtual={String(dados.fator_sensibilidade)}
                sufixo=" mg/dL por U"
                onSalvo={(v) => setDados({ ...dados, fator_sensibilidade: Number(v) })}
              />
              <EditableField
                campo="tempo_insulina_ativa_horas"
                rotulo="Tempo de insulina ativa"
                valorAtual={dados.tempo_insulina_ativa_horas != null ? String(dados.tempo_insulina_ativa_horas) : ""}
                sufixo="h"
                onSalvo={(v) => setDados({ ...dados, tempo_insulina_ativa_horas: Number(v) })}
              />
            </div>
          </Card>

          <div className="flex flex-col gap-6">
            <Card>
              <CardTitulo
                icone={<Utensils size={18} />}
                titulo="Relação insulina:carboidrato"
                descricao="Gramas cobertas por 1 unidade, por período."
              />
              <Lista
                vazio={dados.relacoes_ic.length === 0}
                itens={dados.relacoes_ic.map((r) => ({
                  rotulo: r.periodo,
                  detalhe: `${r.hora_inicio}–${r.hora_fim}`,
                  valor: `${r.gramas_por_unidade}g/U`,
                }))}
              />
            </Card>

            <Card>
              <CardTitulo icone={<Clock size={18} />} titulo="Insulina basal" descricao="Horários e doses diárias." />
              <Lista
                vazio={dados.basal.length === 0}
                itens={dados.basal.map((b) => ({
                  rotulo: b.horario,
                  detalhe: b.tipo_insulina ?? undefined,
                  valor: `${b.dose}U`,
                }))}
              />
            </Card>

            {dados.modificadores.length > 0 && (
              <Card>
                <CardTitulo
                  icone={<SlidersHorizontal size={18} />}
                  titulo="Modificadores"
                  descricao="Ajustes aplicados ao bolus quando ativos."
                />
                <Lista
                  vazio={false}
                  itens={dados.modificadores.map((m) => ({
                    rotulo: m.nome,
                    detalhe: m.ativo ? "Ativo" : "Inativo",
                    apagado: !m.ativo,
                    valor: `${m.valor_ajuste >= 0 ? "+" : ""}${m.valor_ajuste}${m.tipo_ajuste === "percentual" ? "%" : "U"}`,
                  }))}
                />
              </Card>
            )}

            <p className="flex gap-2 px-1 text-xs leading-relaxed text-muted">
              <Syringe size={14} className="mt-px shrink-0" />
              Relação insulina:carboidrato, basal e modificadores são ajustados pelo WhatsApp.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function Lista({
  itens,
  vazio,
}: {
  itens: { rotulo: string; detalhe?: string; valor: string; apagado?: boolean }[];
  vazio: boolean;
}) {
  if (vazio) return <p className="text-sm text-muted">Nada cadastrado ainda.</p>;
  return (
    <ul className="divide-y divide-border">
      {itens.map((i, idx) => (
        <li key={idx} className={`flex items-center justify-between py-3 text-sm first:pt-0 last:pb-0 ${i.apagado ? "opacity-55" : ""}`}>
          <span>
            <span className="font-medium capitalize">{i.rotulo}</span>
            {i.detalhe && <span className="ml-2 text-muted">{i.detalhe}</span>}
          </span>
          <span className="rounded-lg bg-surface px-2.5 py-1 font-semibold">{i.valor}</span>
        </li>
      ))}
    </ul>
  );
}
