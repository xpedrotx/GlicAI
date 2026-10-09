"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronRight, KeyRound, TriangleAlert, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useMedico } from "@/lib/medico-context";
import { tempoDesde } from "@/lib/clinico";
import type { ResumoPaciente } from "@/lib/types";
import { Card, PageHeader, Skeleton, Vazio } from "@/components/ui";
import { useAgora } from "@/components/graficos";

function corDaLeitura(p: ResumoPaciente): string | undefined {
  const v = p.ultima_glicemia?.valor;
  if (v == null || p.limite_baixo == null || p.limite_alto == null) return undefined;
  if (v < p.limite_baixo) return "var(--vermelho)";
  if (v > p.limite_alto) return "var(--accent)";
  return "var(--verde)";
}

export default function PacientesPage() {
  const medico = useMedico();
  const [pacientes, setPacientes] = useState<ResumoPaciente[] | null>(null);
  const [erro, setErro] = useState("");
  const agora = useAgora() * 60_000;

  useEffect(() => {
    api
      .medicoPacientes()
      .then((r) => setPacientes(r.pacientes))
      .catch(() => setErro("Não consegui carregar seus pacientes agora. Tente de novo."));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Pacientes"
        descricao="Quem vinculou você. Você só visualiza: nada do que está aqui pode ser alterado."
      />

      {erro && (
        <Card>
          <Vazio icone={<TriangleAlert size={20} />} titulo={erro} />
        </Card>
      )}

      {!pacientes && !erro && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-[170px]" />
          <Skeleton className="h-[170px]" />
        </div>
      )}

      {pacientes && pacientes.length === 0 && (
        <Card className="max-w-2xl">
          <Vazio
            icone={<Users size={20} />}
            titulo="Nenhum paciente vinculado ainda"
            texto="Passe o seu código de vinculação para o paciente. Assim que ele confirmar, ele aparece aqui."
          />
          <div className="mx-auto mt-2 flex max-w-xs flex-col items-center gap-3">
            <p className="font-heading text-3xl font-extrabold tracking-[0.12em] text-primary">{medico.codigo_vinculo}</p>
            <Link href="/medico/vinculacao" className="text-sm font-semibold text-primary hover:underline">
              Como o paciente usa o código
            </Link>
          </div>
        </Card>
      )}

      {pacientes && pacientes.length > 0 && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {pacientes.map((p) => (
              <Link
                key={p.id}
                href={`/medico/pacientes/${p.id}`}
                className="group rounded-2xl border border-border bg-card p-5 shadow-[var(--sombra)] transition hover:border-primary/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-heading text-lg font-bold">{p.nome ?? "Paciente sem nome"}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {p.ultima_glicemia ? `Última medição ${tempoDesde(p.ultima_glicemia.horario, agora)}` : "Sem medições nos últimos 14 dias"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {p.ultima_fora_da_faixa && (
                      <span className="rounded-full bg-vermelho/10 px-2.5 py-1 text-[11px] font-semibold text-vermelho">
                        Fora da faixa
                      </span>
                    )}
                    <ChevronRight size={18} className="text-muted transition group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-4 gap-3">
                  <Numero rotulo="Última" valor={p.ultima_glicemia ? String(p.ultima_glicemia.valor) : "—"} cor={corDaLeitura(p)} />
                  <Numero rotulo="Média 14d" valor={p.media != null ? String(p.media) : "—"} />
                  <Numero
                    rotulo="No alvo"
                    valor={p.na_faixa_pct != null ? `${p.na_faixa_pct}%` : "—"}
                    cor={p.na_faixa_pct != null && p.na_faixa_pct >= 70 ? "var(--verde)" : undefined}
                  />
                  <Numero
                    rotulo="Hipo/Hiper"
                    valor={`${p.hipoglicemias}/${p.hiperglicemias}`}
                    cor={p.hipoglicemias + p.hiperglicemias > 0 ? "var(--vermelho)" : undefined}
                  />
                </div>
              </Link>
            ))}
          </div>
          <p className="flex items-center gap-2 text-xs text-muted">
            <KeyRound size={14} /> Resumo dos últimos 14 dias. Clique em um paciente para ver os gráficos e o histórico completo.
          </p>
        </>
      )}
    </div>
  );
}

function Numero({ rotulo, valor, cor }: { rotulo: string; valor: string; cor?: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium text-muted">{rotulo}</p>
      <p className="mt-0.5 font-heading text-xl font-bold" style={cor ? { color: cor } : undefined}>
        {valor}
      </p>
    </div>
  );
}
