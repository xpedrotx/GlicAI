"use client";

import { CalendarDays, ChartColumn, ChartPie, Clock, Droplet, Gauge, Syringe, Target, TriangleAlert } from "lucide-react";
import type { Historico } from "@/lib/types";
import { classificarGlicemia, corParaCss, formatarContexto, formatarData, formatarHorario } from "@/lib/clinico";
import { Card, CardTitulo, Skeleton, StatCard, Vazio } from "@/components/ui";
import { GraficoHoje, GraficoMensal, GraficoPeriodos, PizzaTempoNoAlvo } from "@/components/graficos";

/**
 * Visão geral de glicemia de um paciente: cartões-resumo, gráficos e tabela.
 * Usada pelo painel do próprio paciente e pelo painel do médico — as duas
 * telas mostram exatamente os mesmos números.
 */
export function VisaoGeralPaciente({
  dados,
  dias,
  textoSemDados,
  mostrarDoses = false,
}: {
  dados: Historico;
  dias: number;
  textoSemDados: string;
  mostrarDoses?: boolean;
}) {
  return (
    <>
      <Resumo dados={dados} textoSemDados={textoSemDados} />
      <Graficos dados={dados} dias={dias} />
      <TabelaGlicemias dados={dados} />
      {mostrarDoses && <TabelaDoses dados={dados} />}
    </>
  );
}

export function CarregandoPainel() {
  return (
    <>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[108px]" />
        ))}
      </div>
      <Skeleton className="h-[400px]" />
    </>
  );
}

function Graficos({ dados, dias }: { dados: Historico; dias: number }) {
  const perfil = dados.perfil!;
  const tz = dados.timezone ?? "America/Sao_Paulo";
  const { glicemias } = dados;
  const hoje = new Date().toLocaleDateString("pt-BR", { timeZone: tz, weekday: "long", day: "numeric", month: "long" });

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardTitulo icone={<Clock size={18} />} titulo="Hoje" descricao={hoje.charAt(0).toUpperCase() + hoje.slice(1)} />
          <GraficoHoje glicemias={glicemias} perfil={perfil} timezone={tz} />
        </Card>
        <Card>
          <CardTitulo icone={<ChartPie size={18} />} titulo="Tempo no alvo" descricao={`Últimos ${dias} dias`} />
          <PizzaTempoNoAlvo glicemias={glicemias} perfil={perfil} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardTitulo
            icone={<CalendarDays size={18} />}
            titulo="Mês"
            descricao={`Média de cada dia nos últimos ${dias} dias · faixa-alvo ${perfil.limite_baixo}–${perfil.limite_alto} mg/dL`}
          />
          <GraficoMensal glicemias={glicemias} perfil={perfil} timezone={tz} dias={dias} />
        </Card>
        <Card>
          <CardTitulo icone={<ChartColumn size={18} />} titulo="Por período do dia" descricao="Média em cada parte do dia" />
          <GraficoPeriodos glicemias={glicemias} perfil={perfil} timezone={tz} />
        </Card>
      </div>
    </>
  );
}

function Resumo({ dados, textoSemDados }: { dados: Historico; textoSemDados: string }) {
  const { glicemias, perfil } = dados;
  if (!perfil || glicemias.length === 0) {
    return (
      <Card>
        <Vazio icone={<Droplet size={20} />} titulo="Sem glicemias nesse período" texto={textoSemDados} />
      </Card>
    );
  }

  const valores = glicemias.map((g) => g.valor);
  const media = valores.reduce((a, b) => a + b, 0) / valores.length;
  const naFaixa = valores.filter((v) => v >= perfil.limite_baixo && v <= perfil.limite_alto).length;
  const pctFaixa = Math.round((100 * naFaixa) / valores.length);
  const hipos = valores.filter((v) => v < perfil.limite_baixo).length;
  const hipers = valores.filter((v) => v > perfil.limite_alto).length;
  const tz = dados.timezone ?? "America/Sao_Paulo";
  const diasComDados = new Set(glicemias.map((g) => formatarData(g.horario, tz))).size || 1;

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard rotulo="Média" valor={`${media.toFixed(0)}`} detalhe="mg/dL no período" icone={<Gauge size={17} />} />
      <StatCard
        rotulo="Tempo no alvo"
        valor={`${pctFaixa}%`}
        detalhe={`${naFaixa} de ${valores.length} medições`}
        corValor={pctFaixa >= 70 ? "var(--verde)" : undefined}
        icone={<Target size={17} />}
      />
      <StatCard
        rotulo="Hipo / Hiper"
        valor={`${hipos} / ${hipers}`}
        detalhe="fora da faixa"
        corValor={hipos + hipers > 0 ? "var(--vermelho)" : undefined}
        icone={<TriangleAlert size={17} />}
      />
      <StatCard
        rotulo="Medições"
        valor={String(valores.length)}
        detalhe={`${(valores.length / diasComDados).toFixed(1)} por dia medido`}
        icone={<Droplet size={17} />}
      />
    </div>
  );
}

function TabelaGlicemias({ dados }: { dados: Historico }) {
  const { glicemias, perfil, timezone } = dados;
  if (!perfil) return null;
  const tz = timezone ?? "America/Sao_Paulo";
  const ordenadas = [...glicemias].sort((a, b) => new Date(b.horario).getTime() - new Date(a.horario).getTime());

  return (
    <Card className="p-0">
      <div className="px-6 pt-6">
        <CardTitulo icone={<Droplet size={18} />} titulo="Registros" descricao="Do mais recente para o mais antigo." />
      </div>
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-card">
            <tr className="border-y border-border text-left text-xs font-medium text-muted">
              <th className="px-6 py-3 font-medium">Data e hora</th>
              <th className="px-6 py-3 font-medium">Glicemia</th>
              <th className="px-6 py-3 font-medium">Momento</th>
            </tr>
          </thead>
          <tbody>
            {ordenadas.length === 0 && (
              <tr>
                <td colSpan={3} className="px-6 py-8 text-center text-muted">
                  Sem registros nesse período.
                </td>
              </tr>
            )}
            {ordenadas.map((g, i) => {
              const { cor, seta } = classificarGlicemia(g.valor, perfil.limite_baixo, perfil.meta_glicemia, perfil.limite_alto);
              return (
                <tr key={i} className="border-b border-border transition last:border-0 hover:bg-surface">
                  <td className="whitespace-nowrap px-6 py-3 text-foreground/80">{formatarHorario(g.horario, tz)}</td>
                  <td className="whitespace-nowrap px-6 py-3">
                    <span className="font-semibold" style={{ color: corParaCss(cor) }}>
                      {g.valor} {seta}
                    </span>{" "}
                    <span className="text-xs text-muted">mg/dL</span>
                  </td>
                  <td className="px-6 py-3 text-foreground/80">{formatarContexto(g.contexto)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function TabelaDoses({ dados }: { dados: Historico }) {
  const tz = dados.timezone ?? "America/Sao_Paulo";
  const doses = [...dados.bolus].sort((a, b) => new Date(b.horario).getTime() - new Date(a.horario).getTime());
  const vazio = (v: number | null) => (v == null ? "—" : String(v));

  return (
    <Card className="p-0">
      <div className="px-6 pt-6">
        <CardTitulo
          icone={<Syringe size={18} />}
          titulo="Doses de insulina"
          descricao="Doses calculadas pelo GlicAI e o que o paciente informou ter aplicado."
        />
      </div>
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-card">
            <tr className="border-y border-border text-left text-xs font-medium text-muted">
              <th className="px-6 py-3 font-medium">Data e hora</th>
              <th className="px-4 py-3 font-medium">Carbo (g)</th>
              <th className="px-4 py-3 font-medium">Glicemia ref.</th>
              <th className="px-4 py-3 font-medium">Calculada</th>
              <th className="px-4 py-3 font-medium">Aplicada</th>
            </tr>
          </thead>
          <tbody>
            {doses.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-muted">
                  Nenhuma dose registrada nesse período.
                </td>
              </tr>
            )}
            {doses.map((d, i) => (
              <tr key={i} className="border-b border-border transition last:border-0 hover:bg-surface">
                <td className="whitespace-nowrap px-6 py-3 text-foreground/80">{formatarHorario(d.horario, tz)}</td>
                <td className="px-4 py-3">{vazio(d.carboidratos_g)}</td>
                <td className="px-4 py-3">{vazio(d.glicemia_referencia)}</td>
                <td className="px-4 py-3">{d.dose_calculada == null ? "—" : `${d.dose_calculada}U`}</td>
                <td className="px-4 py-3 font-semibold">{d.dose_aplicada == null ? "não aplicada" : `${d.dose_aplicada}U`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
