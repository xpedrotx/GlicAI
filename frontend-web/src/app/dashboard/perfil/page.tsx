"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PerfilCompleto } from "@/lib/types";
import { Card } from "@/components/ui";
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

  if (carregando) return <p className="text-sm text-muted">Carregando...</p>;
  if (erro) return <p className="text-sm text-primary">{erro}</p>;
  if (!dados) return null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-heading text-2xl font-semibold">Perfil e configurações</h1>

      <Card>
        <h2 className="mb-1 font-heading text-lg font-semibold">Dados gerais</h2>
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

      <Card>
        <h2 className="mb-3 font-heading text-lg font-semibold">Relação insulina:carboidrato</h2>
        {dados.relacoes_ic.length === 0 ? (
          <p className="text-sm text-muted">Nada cadastrado ainda.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {dados.relacoes_ic.map((r, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-foreground/80">
                  {r.periodo} ({r.hora_inicio}–{r.hora_fim})
                </span>
                <span className="font-medium">{r.gramas_por_unidade}g/U</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 font-heading text-lg font-semibold">Insulina basal</h2>
        {dados.basal.length === 0 ? (
          <p className="text-sm text-muted">Nada cadastrado ainda.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {dados.basal.map((b, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-foreground/80">
                  {b.horario}
                  {b.tipo_insulina ? ` (${b.tipo_insulina})` : ""}
                </span>
                <span className="font-medium">{b.dose}U</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {dados.modificadores.length > 0 && (
        <Card>
          <h2 className="mb-3 font-heading text-lg font-semibold">Modificadores</h2>
          <ul className="flex flex-col gap-2.5">
            {dados.modificadores.map((m, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-foreground/80">
                  {m.nome} {!m.ativo && <span className="text-muted">(inativo)</span>}
                </span>
                <span className="font-medium">
                  {m.valor_ajuste >= 0 ? "+" : ""}
                  {m.valor_ajuste}
                  {m.tipo_ajuste === "percentual" ? "%" : "U"}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
