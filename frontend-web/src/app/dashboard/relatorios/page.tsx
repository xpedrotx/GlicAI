"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HbA1c, Padroes, Relatorio } from "@/lib/types";
import { Card, StatCard } from "@/components/ui";

const PERIODOS = [
  { valor: "semana" as const, rotulo: "Semana" },
  { valor: "mes" as const, rotulo: "Mês" },
];

export default function RelatoriosPage() {
  const [periodo, setPeriodo] = useState<"semana" | "mes">("semana");
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [hba1c, setHba1c] = useState<HbA1c | null>(null);
  const [padroes, setPadroes] = useState<Padroes | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    setCarregando(true);
    api
      .relatorio(periodo)
      .then(setRelatorio)
      .finally(() => setCarregando(false));
  }, [periodo]);

  useEffect(() => {
    api.hba1c(90).then(setHba1c);
    api.padroes(60).then(setPadroes);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-heading text-2xl font-semibold">Relatórios</h1>
        <div className="flex gap-1 rounded-lg border border-border p-1">
          {PERIODOS.map((p) => (
            <button
              key={p.valor}
              onClick={() => setPeriodo(p.valor)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                periodo === p.valor ? "bg-primary text-primary-foreground" : "text-muted hover:text-foreground"
              }`}
            >
              {p.rotulo}
            </button>
          ))}
        </div>
      </div>

      {carregando && <p className="text-sm text-muted">Carregando...</p>}

      {!carregando && relatorio && !relatorio.perfil && (
        <Card>
          <p className="text-sm text-muted">Ainda não achei seu perfil glicêmico — termina o cadastro pelo WhatsApp.</p>
        </Card>
      )}

      {!carregando && relatorio?.perfil && (
        <BlocoRelatorio relatorio={relatorio} />
      )}

      <BlocoHbA1c hba1c={hba1c} />

      <BlocoPadroes padroes={padroes} />
    </div>
  );
}

function BlocoRelatorio({ relatorio }: { relatorio: Relatorio }) {
  const semDados = !relatorio.num_medicoes;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-heading text-lg font-semibold">Resumo do período</h2>

      {semDados ? (
        <Card>
          <p className="text-sm text-muted">Sem registros de glicemia nesse período.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard rotulo="Medições" valor={String(relatorio.num_medicoes)} />
          <StatCard rotulo="Média" valor={`${relatorio.media_glicemia?.toFixed(0)} mg/dL`} />
          <StatCard
            rotulo="Na faixa"
            valor={`${relatorio.na_faixa_pct}%`}
            corValor={(relatorio.na_faixa_pct ?? 0) >= 70 ? "var(--verde)" : undefined}
          />
          <StatCard
            rotulo="Hipo / Hiper"
            valor={`${relatorio.hipoglicemias} / ${relatorio.hiperglicemias}`}
            corValor={
              (relatorio.hipoglicemias ?? 0) + (relatorio.hiperglicemias ?? 0) > 0 ? "var(--vermelho)" : undefined
            }
          />
        </div>
      )}

      {relatorio.doses_aplicadas ? (
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-muted">💉 Insulina</h3>
          <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-muted">Doses aplicadas</p>
              <p className="font-medium">{relatorio.doses_aplicadas}</p>
            </div>
            <div>
              <p className="text-muted">Total no período</p>
              <p className="font-medium">{relatorio.total_insulina?.toFixed(1)}U</p>
            </div>
            <div>
              <p className="text-muted">Média por dia</p>
              <p className="font-medium">{relatorio.media_insulina_dia?.toFixed(1)}U</p>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-muted">💉 Nenhuma dose de insulina registrada no período.</p>
        </Card>
      )}

      {!!relatorio.eventos_criticos && (
        <Card className="border-primary/30">
          <p className="text-sm text-primary">
            🚨 <span className="font-semibold">{relatorio.eventos_criticos}</span> evento(s) crítico(s) de glicemia
            fora da faixa segura nesse período.
          </p>
        </Card>
      )}
    </div>
  );
}

function BlocoHbA1c({ hba1c }: { hba1c: HbA1c | null }) {
  if (!hba1c) return null;

  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-heading text-lg font-semibold">Estimativa de HbA1c/GMI</h2>
      {!hba1c.disponivel ? (
        <Card>
          <p className="text-sm text-muted">
            Ainda não tenho medições suficientes nos últimos {hba1c.dias} dias pra uma estimativa confiável (mínimo
            de {hba1c.minimo_medicoes}). Continue registrando suas glicemias.
          </p>
        </Card>
      ) : (
        <Card>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Glicemia média</p>
              <p className="font-heading text-xl font-semibold">{hba1c.media_glicemia.toFixed(0)} mg/dL</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">GMI estimado</p>
              <p className="font-heading text-xl font-semibold">{hba1c.gmi.toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Baseado em</p>
              <p className="font-heading text-xl font-semibold">{hba1c.num_medicoes} medições</p>
            </div>
          </div>
          <p className="mt-4 text-xs text-muted">
            ⚠️ Estimativa aproximada baseada nas suas medições manuais (não num sensor contínuo) — não substitui o
            exame de sangue de HbA1c. Use como referência pra conversar com seu médico.
          </p>
        </Card>
      )}
    </div>
  );
}

function BlocoPadroes({ padroes }: { padroes: Padroes | null }) {
  if (!padroes) return null;

  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-heading text-lg font-semibold">Padrões detectados</h2>
      {padroes.padroes.length === 0 ? (
        <Card>
          <p className="text-sm text-muted">
            Não encontrei nenhum padrão claro nos últimos {padroes.dias} dias — ou ainda faltam medições suficientes
            pra detectar algo com confiança.
          </p>
        </Card>
      ) : (
        <Card>
          <ul className="flex flex-col gap-3">
            {padroes.padroes.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span>{p.tipo === "alta" ? "🟠" : "🔴"}</span>
                <span>
                  Toda <span className="font-medium">{p.dia_semana_label}</span> {p.periodo}, sua glicemia costuma{" "}
                  {p.tipo === "alta" ? "vir alta" : "vir baixa"} (média{" "}
                  <span className="font-medium">{p.media.toFixed(0)} mg/dL</span> em {p.n} medições)
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted">
            Vale comentar isso com seu médico pra ajustar basal/relação IC nesses horários.
          </p>
        </Card>
      )}
    </div>
  );
}
