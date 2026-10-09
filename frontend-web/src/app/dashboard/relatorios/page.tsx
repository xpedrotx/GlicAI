"use client";

import { useEffect, useState } from "react";
import { CalendarDays, Droplet, Gauge, Info, Sparkles, Syringe, Target, TriangleAlert, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import type { HbA1c, Padroes, Relatorio } from "@/lib/types";
import { Card, CardTitulo, PageHeader, Segmentado, Skeleton, StatCard, Vazio } from "@/components/ui";

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
      <PageHeader
        titulo="Relatórios"
        descricao="Resumo do período, estimativa de HbA1c e padrões que se repetem."
        acao={<Segmentado opcoes={PERIODOS} valor={periodo} aoMudar={setPeriodo} />}
      />

      {carregando && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[108px]" />
          ))}
        </div>
      )}

      {!carregando && relatorio && !relatorio.perfil && (
        <Card>
          <Vazio
            icone={<Droplet size={20} />}
            titulo="Seu perfil ainda não está completo"
            texto="Termine o cadastro pelo WhatsApp para gerar relatórios."
          />
        </Card>
      )}

      {!carregando && relatorio?.perfil && <BlocoRelatorio relatorio={relatorio} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <BlocoHbA1c hba1c={hba1c} />
        <BlocoPadroes padroes={padroes} />
      </div>
    </div>
  );
}

function BlocoRelatorio({ relatorio }: { relatorio: Relatorio }) {
  const semDados = !relatorio.num_medicoes;

  return (
    <div className="flex flex-col gap-4">
      {semDados ? (
        <Card>
          <Vazio icone={<CalendarDays size={20} />} titulo="Sem glicemias registradas nesse período" />
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard rotulo="Medições" valor={String(relatorio.num_medicoes)} icone={<Droplet size={17} />} />
          <StatCard
            rotulo="Média"
            valor={`${relatorio.media_glicemia?.toFixed(0)}`}
            detalhe="mg/dL"
            icone={<Gauge size={17} />}
          />
          <StatCard
            rotulo="Tempo no alvo"
            valor={`${relatorio.na_faixa_pct}%`}
            corValor={(relatorio.na_faixa_pct ?? 0) >= 70 ? "var(--verde)" : undefined}
            icone={<Target size={17} />}
          />
          <StatCard
            rotulo="Hipo / Hiper"
            valor={`${relatorio.hipoglicemias} / ${relatorio.hiperglicemias}`}
            corValor={(relatorio.hipoglicemias ?? 0) + (relatorio.hiperglicemias ?? 0) > 0 ? "var(--vermelho)" : undefined}
            icone={<TriangleAlert size={17} />}
          />
        </div>
      )}

      {!!relatorio.eventos_criticos && (
        <div className="flex items-center gap-3 rounded-2xl border border-vermelho/25 bg-vermelho/10 px-5 py-4 text-sm">
          <TriangleAlert size={18} className="shrink-0 text-vermelho" />
          <p>
            <span className="font-semibold">{relatorio.eventos_criticos}</span> evento(s) crítico(s) de glicemia fora
            da faixa segura nesse período.
          </p>
        </div>
      )}

      <Card>
        <CardTitulo icone={<Syringe size={18} />} titulo="Insulina" descricao="Doses registradas como aplicadas." />
        {relatorio.doses_aplicadas ? (
          <div className="grid grid-cols-3 divide-x divide-border">
            {[
              { r: "Doses aplicadas", v: String(relatorio.doses_aplicadas) },
              { r: "Total no período", v: `${relatorio.total_insulina?.toFixed(1)}U` },
              { r: "Média por dia", v: `${relatorio.media_insulina_dia?.toFixed(1)}U` },
            ].map((c) => (
              <div key={c.r} className="px-4 first:pl-0">
                <p className="text-[13px] text-muted">{c.r}</p>
                <p className="mt-1 font-heading text-xl font-bold">{c.v}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">Nenhuma dose de insulina registrada no período.</p>
        )}
      </Card>
    </div>
  );
}

function BlocoHbA1c({ hba1c }: { hba1c: HbA1c | null }) {
  if (!hba1c) return <Skeleton className="h-[220px]" />;

  return (
    <Card>
      <CardTitulo
        icone={<Gauge size={18} />}
        titulo="Estimativa de HbA1c (GMI)"
        descricao={`Baseada nos últimos ${hba1c.dias} dias.`}
      />
      {!hba1c.disponivel ? (
        <p className="text-sm leading-relaxed text-muted">
          Ainda não há medições suficientes para uma estimativa confiável (mínimo de {hba1c.minimo_medicoes}). Continue
          registrando suas glicemias.
        </p>
      ) : (
        <>
          <div className="flex items-end gap-6">
            <div>
              <p className="font-heading text-5xl font-extrabold tracking-tight">{hba1c.gmi.toFixed(1)}%</p>
              <p className="mt-1 text-sm text-muted">GMI estimado</p>
            </div>
            <div className="mb-1 flex flex-col gap-1 text-sm">
              <p>
                <span className="font-semibold">{hba1c.media_glicemia.toFixed(0)} mg/dL</span>{" "}
                <span className="text-muted">de média</span>
              </p>
              <p>
                <span className="font-semibold">{hba1c.num_medicoes}</span> <span className="text-muted">medições</span>
              </p>
            </div>
          </div>
          <p className="mt-5 flex gap-2 rounded-xl bg-surface px-3.5 py-3 text-xs leading-relaxed text-muted">
            <Info size={15} className="mt-px shrink-0" />
            Estimativa aproximada a partir de medições manuais, não de um sensor contínuo. Não substitui o exame de
            sangue — use como referência para conversar com seu médico.
          </p>
        </>
      )}
    </Card>
  );
}

function BlocoPadroes({ padroes }: { padroes: Padroes | null }) {
  if (!padroes) return <Skeleton className="h-[220px]" />;

  return (
    <Card>
      <CardTitulo
        icone={<Sparkles size={18} />}
        titulo="Padrões detectados"
        descricao={`Horários que se repetem nos últimos ${padroes.dias} dias.`}
      />
      {padroes.padroes.length === 0 ? (
        <p className="text-sm leading-relaxed text-muted">
          Nenhum padrão claro por enquanto — ou ainda faltam medições para detectar algo com confiança.
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-2.5">
            {padroes.padroes.map((p, i) => (
              <li key={i} className="flex items-start gap-3 rounded-xl border border-border px-3.5 py-3 text-sm">
                <span
                  className="mt-0.5 shrink-0"
                  style={{ color: p.tipo === "alta" ? "var(--accent)" : "var(--vermelho)" }}
                >
                  {p.tipo === "alta" ? <TrendingUp size={17} /> : <TrendingDown size={17} />}
                </span>
                <span className="leading-relaxed">
                  <span className="font-semibold">
                    {p.dia_semana_label}, {p.periodo}
                  </span>{" "}
                  — costuma vir {p.tipo === "alta" ? "alta" : "baixa"} (média{" "}
                  <span className="font-semibold">{p.media.toFixed(0)} mg/dL</span> em {p.n} medições)
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted">
            Vale comentar com seu médico para ajustar basal ou relação insulina:carboidrato nesses horários.
          </p>
        </>
      )}
    </Card>
  );
}
