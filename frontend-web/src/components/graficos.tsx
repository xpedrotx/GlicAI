"use client";

import { useSyncExternalStore } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Glicemia, Perfil } from "@/lib/types";
import { formatarContexto } from "@/lib/clinico";

/*
 * Gráficos da visão geral. Cores seguem o significado clínico: verde no
 * alvo, âmbar acima, vermelho abaixo — iguais em todos os gráficos.
 */

export type Faixa = "baixa" | "alvo" | "alta";

export const COR: Record<Faixa, string> = { baixa: "var(--vermelho)", alvo: "var(--verde)", alta: "var(--accent)" };
export const ROTULO: Record<Faixa, string> = { baixa: "Abaixo do alvo", alvo: "No alvo", alta: "Acima do alvo" };
const FAIXAS: Faixa[] = ["baixa", "alvo", "alta"];

export function faixaDe(valor: number, perfil: Perfil): Faixa {
  if (valor < perfil.limite_baixo) return "baixa";
  if (valor > perfil.limite_alto) return "alta";
  return "alvo";
}

/** Data (aaaa-mm-dd) e hora decimal de um instante, no fuso do paciente. */
export function partesNoFuso(data: Date, tz: string): { dia: string; hora: number } {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(data)
      .map((x) => [x.type, x.value])
  );
  return { dia: `${p.year}-${p.month}-${p.day}`, hora: Number(p.hour) + Number(p.minute) / 60 };
}

const eixo = { stroke: "var(--muted)", fontSize: 12, axisLine: false, tickLine: false } as const;

function ticksY(perfil: Perfil, yMin: number, yMax: number): number[] {
  const limites = [perfil.limite_baixo, perfil.limite_alto];
  return [
    ...limites,
    ...[0, 50, 250, 300, 350, 400, 450].filter((v) => v >= yMin && v <= yMax && limites.every((l) => Math.abs(v - l) > 25)),
  ].sort((a, b) => a - b);
}

function FaixaAlvo({ perfil }: { perfil: Perfil }) {
  return (
    <>
      <ReferenceArea y1={perfil.limite_baixo} y2={perfil.limite_alto} fill="var(--verde)" fillOpacity={0.08} ifOverflow="hidden" />
      <ReferenceLine y={perfil.limite_alto} stroke="var(--accent)" strokeOpacity={0.5} strokeDasharray="5 5" />
      <ReferenceLine y={perfil.limite_baixo} stroke="var(--vermelho)" strokeOpacity={0.5} strokeDasharray="5 5" />
    </>
  );
}

function CaixaDica({ children }: { children: React.ReactNode }) {
  return <div className="min-w-[150px] rounded-xl border border-border bg-card px-3.5 py-2.5 text-sm shadow-lg">{children}</div>;
}

function ValorDica({ valor, faixa, sufixo = "mg/dL" }: { valor: number; faixa: Faixa; sufixo?: string }) {
  return (
    <>
      <div className="flex items-baseline gap-1.5">
        <span className="font-heading text-lg font-bold" style={{ color: COR[faixa] }}>
          {valor}
        </span>
        <span className="text-xs text-muted">{sufixo}</span>
      </div>
      <p className="text-xs font-medium" style={{ color: COR[faixa] }}>
        {ROTULO[faixa]}
      </p>
    </>
  );
}

export function Legenda() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      {FAIXAS.map((f) => (
        <span key={f} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: COR[f] }} />
          {ROTULO[f]}
        </span>
      ))}
    </div>
  );
}

function useAgora(): number {
  // relógio de minuto em minuto, pra linha "agora" do gráfico de hoje
  return useSyncExternalStore(
    (avisar) => {
      const id = setInterval(avisar, 60_000);
      return () => clearInterval(id);
    },
    () => Math.floor(Date.now() / 60_000),
    () => 0
  );
}

// --------------------------------------------------------------------------
// Hoje — linha com as medições do dia
// --------------------------------------------------------------------------

type PontoHoje = { hora: number; valor: number; faixa: Faixa; contexto: string | null; rotuloHora: string };

export function GraficoHoje({ glicemias, perfil, timezone }: { glicemias: Glicemia[]; perfil: Perfil; timezone: string }) {
  const minuto = useAgora();
  const agora = partesNoFuso(new Date(minuto * 60_000), timezone);

  const pontos: PontoHoje[] = glicemias
    .map((g) => ({ g, p: partesNoFuso(new Date(g.horario), timezone) }))
    .filter(({ p }) => p.dia === agora.dia)
    .map(({ g, p }) => ({
      hora: p.hora,
      valor: g.valor,
      faixa: faixaDe(g.valor, perfil),
      contexto: g.contexto,
      rotuloHora: `${String(Math.floor(p.hora)).padStart(2, "0")}:${String(Math.round((p.hora % 1) * 60)).padStart(2, "0")}`,
    }))
    .sort((a, b) => a.hora - b.hora);

  if (pontos.length === 0) {
    return (
      <div className="flex h-[260px] flex-col items-center justify-center text-center">
        <p className="text-sm font-medium">Nenhuma medição hoje ainda</p>
        <p className="mt-1 max-w-xs text-sm text-muted">Mande sua glicemia para o GlicAI no WhatsApp — ex: “tá 120”.</p>
      </div>
    );
  }

  const valores = pontos.map((p) => p.valor);
  const yMin = Math.max(0, Math.floor((Math.min(...valores, perfil.limite_baixo) - 20) / 10) * 10);
  const yMax = Math.ceil((Math.max(...valores, perfil.limite_alto) + 20) / 50) * 50;

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={pontos} margin={{ top: 16, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
        <FaixaAlvo perfil={perfil} />
        <ReferenceLine
          x={agora.hora}
          stroke="var(--muted)"
          strokeDasharray="2 3"
          label={{ value: "agora", position: "top", fill: "var(--muted)", fontSize: 11 }}
        />
        <XAxis
          {...eixo}
          dataKey="hora"
          type="number"
          domain={[0, 24]}
          ticks={[0, 3, 6, 9, 12, 15, 18, 21, 24]}
          tickFormatter={(h: number) => `${String(h).padStart(2, "0")}h`}
          tickMargin={10}
        />
        <YAxis {...eixo} domain={[yMin, yMax]} ticks={ticksY(perfil, yMin, yMax)} width={48} />
        <Tooltip
          cursor={{ stroke: "var(--muted)", strokeDasharray: "3 3", strokeOpacity: 0.5 }}
          content={({ active, payload }) => {
            const p = active && payload?.[0]?.payload as PontoHoje | undefined;
            if (!p) return null;
            return (
              <CaixaDica>
                <ValorDica valor={p.valor} faixa={p.faixa} />
                <p className="mt-1.5 text-xs text-muted">
                  Hoje, {p.rotuloHora}
                  {p.contexto && p.contexto !== "outro" ? ` · ${formatarContexto(p.contexto)}` : ""}
                </p>
              </CaixaDica>
            );
          }}
        />
        <Line
          dataKey="valor"
          type="linear"
          stroke="var(--foreground)"
          strokeOpacity={0.35}
          strokeWidth={2}
          isAnimationActive={false}
          dot={(props: { cx?: number; cy?: number; payload?: PontoHoje; index?: number }) => (
            <circle
              key={props.index}
              cx={props.cx}
              cy={props.cy}
              r={6}
              fill={props.payload ? COR[props.payload.faixa] : "none"}
              stroke="var(--card)"
              strokeWidth={2}
            />
          )}
          activeDot={{ r: 8, stroke: "var(--card)", strokeWidth: 2 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------
// Mês — colunas com a média de cada dia
// --------------------------------------------------------------------------

type DiaMes = { rotulo: string; media: number | null; min: number; max: number; n: number; faixa: Faixa | null };

export function GraficoMensal({
  glicemias,
  perfil,
  timezone,
  dias = 30,
}: {
  glicemias: Glicemia[];
  perfil: Perfil;
  timezone: string;
  dias?: number;
}) {
  const porDia = new Map<string, number[]>();
  for (const g of glicemias) {
    const { dia } = partesNoFuso(new Date(g.horario), timezone);
    porDia.set(dia, [...(porDia.get(dia) ?? []), g.valor]);
  }

  // todos os dias do período, inclusive os sem medição (coluna vazia)
  const hoje = useAgora() * 60_000;
  const serie: DiaMes[] = Array.from({ length: dias }, (_, i) => {
    const { dia } = partesNoFuso(new Date(hoje - (dias - 1 - i) * 86_400_000), timezone);
    const vals = porDia.get(dia) ?? [];
    const media = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
    return {
      rotulo: `${dia.slice(8, 10)}/${dia.slice(5, 7)}`,
      media,
      min: vals.length ? Math.min(...vals) : 0,
      max: vals.length ? Math.max(...vals) : 0,
      n: vals.length,
      faixa: media == null ? null : faixaDe(media, perfil),
    };
  });

  const medias = serie.flatMap((d) => (d.media == null ? [] : [d.media]));
  if (medias.length === 0) {
    return <p className="flex h-[280px] items-center justify-center text-sm text-muted">Sem medições nos últimos {dias} dias.</p>;
  }
  const yMax = Math.ceil((Math.max(...medias, perfil.limite_alto) + 20) / 50) * 50;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={serie} margin={{ top: 10, right: 8, bottom: 0, left: -8 }} barCategoryGap="22%">
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
        <FaixaAlvo perfil={perfil} />
        <XAxis {...eixo} dataKey="rotulo" interval="preserveStartEnd" minTickGap={18} tickMargin={10} />
        <YAxis {...eixo} domain={[0, yMax]} ticks={ticksY(perfil, 0, yMax)} width={48} />
        <Tooltip
          cursor={{ fill: "var(--foreground)", fillOpacity: 0.05 }}
          content={({ active, payload }) => {
            const d = active && (payload?.[0]?.payload as DiaMes | undefined);
            if (!d) return null;
            return (
              <CaixaDica>
                <p className="mb-1 text-xs font-semibold text-muted">{d.rotulo}</p>
                {d.media == null || !d.faixa ? (
                  <p className="text-xs text-muted">Sem medições</p>
                ) : (
                  <>
                    <ValorDica valor={d.media} faixa={d.faixa} sufixo="mg/dL de média" />
                    <p className="mt-1.5 text-xs text-muted">
                      {d.n} {d.n === 1 ? "medição" : "medições"} · de {d.min} a {d.max}
                    </p>
                  </>
                )}
              </CaixaDica>
            );
          }}
        />
        <Bar dataKey="media" radius={[6, 6, 2, 2]} isAnimationActive={false} maxBarSize={28}>
          {serie.map((d, i) => (
            <Cell key={i} fill={d.faixa ? COR[d.faixa] : "transparent"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------
// Pizza — tempo no alvo
// --------------------------------------------------------------------------

export function PizzaTempoNoAlvo({ glicemias, perfil }: { glicemias: Glicemia[]; perfil: Perfil }) {
  const total = glicemias.length;
  const contagem = { baixa: 0, alvo: 0, alta: 0 } as Record<Faixa, number>;
  for (const g of glicemias) contagem[faixaDe(g.valor, perfil)] += 1;
  const pct = (f: Faixa) => (total ? Math.round((100 * contagem[f]) / total) : 0);
  const dados = FAIXAS.filter((f) => contagem[f] > 0).map((f) => ({ faixa: f, valor: contagem[f] }));

  if (total === 0) {
    return <p className="flex h-[260px] items-center justify-center text-sm text-muted">Sem medições no período.</p>;
  }

  return (
    <div>
      <div className="relative h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={dados}
              dataKey="valor"
              nameKey="faixa"
              innerRadius="64%"
              outerRadius="92%"
              paddingAngle={dados.length > 1 ? 3 : 0}
              cornerRadius={6}
              stroke="none"
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            >
              {dados.map((d) => (
                <Cell key={d.faixa} fill={COR[d.faixa]} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                const d = active && (payload?.[0]?.payload as { faixa: Faixa; valor: number } | undefined);
                if (!d) return null;
                return (
                  <CaixaDica>
                    <p className="text-xs font-semibold" style={{ color: COR[d.faixa] }}>
                      {ROTULO[d.faixa]}
                    </p>
                    <p className="text-xs text-muted">
                      {d.valor} de {total} medições ({pct(d.faixa)}%)
                    </p>
                  </CaixaDica>
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-heading text-3xl font-extrabold" style={{ color: pct("alvo") >= 70 ? "var(--verde)" : undefined }}>
            {pct("alvo")}%
          </span>
          <span className="text-xs text-muted">no alvo</span>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {FAIXAS.map((f) => (
          <div key={f} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-foreground/80">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: COR[f] }} />
              {ROTULO[f]}
            </span>
            <span className="font-semibold">{pct(f)}%</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted">Meta recomendada: mais de 70% no alvo.</p>
    </div>
  );
}

// --------------------------------------------------------------------------
// Colunas — média por período do dia
// --------------------------------------------------------------------------

const PERIODOS = [
  { nome: "Madrugada", de: 0, ate: 6 },
  { nome: "Manhã", de: 6, ate: 12 },
  { nome: "Tarde", de: 12, ate: 18 },
  { nome: "Noite", de: 18, ate: 24 },
];

type Periodo = { nome: string; faixaHoras: string; media: number | null; n: number; faixa: Faixa | null };

export function GraficoPeriodos({ glicemias, perfil, timezone }: { glicemias: Glicemia[]; perfil: Perfil; timezone: string }) {
  const dados: Periodo[] = PERIODOS.map((p) => {
    const vals = glicemias
      .filter((g) => {
        const h = partesNoFuso(new Date(g.horario), timezone).hora;
        return h >= p.de && h < p.ate;
      })
      .map((g) => g.valor);
    const media = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
    return {
      nome: p.nome,
      faixaHoras: `${String(p.de).padStart(2, "0")}h–${String(p.ate).padStart(2, "0")}h`,
      media,
      n: vals.length,
      faixa: media == null ? null : faixaDe(media, perfil),
    };
  });

  const medias = dados.flatMap((d) => (d.media == null ? [] : [d.media]));
  if (medias.length === 0) {
    return <p className="flex h-[260px] items-center justify-center text-sm text-muted">Sem medições no período.</p>;
  }
  const yMax = Math.ceil((Math.max(...medias, perfil.limite_alto) + 20) / 50) * 50;

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={dados} margin={{ top: 22, right: 8, bottom: 0, left: -8 }} barCategoryGap="28%">
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
        <FaixaAlvo perfil={perfil} />
        <XAxis {...eixo} dataKey="nome" tickMargin={10} />
        <YAxis {...eixo} domain={[0, yMax]} ticks={ticksY(perfil, 0, yMax)} width={48} />
        <Tooltip
          cursor={{ fill: "var(--foreground)", fillOpacity: 0.05 }}
          content={({ active, payload }) => {
            const d = active && (payload?.[0]?.payload as Periodo | undefined);
            if (!d) return null;
            return (
              <CaixaDica>
                <p className="mb-1 text-xs font-semibold text-muted">
                  {d.nome} · {d.faixaHoras}
                </p>
                {d.media == null || !d.faixa ? (
                  <p className="text-xs text-muted">Sem medições</p>
                ) : (
                  <>
                    <ValorDica valor={d.media} faixa={d.faixa} sufixo="mg/dL de média" />
                    <p className="mt-1.5 text-xs text-muted">{d.n} medições</p>
                  </>
                )}
              </CaixaDica>
            );
          }}
        />
        <Bar
          dataKey="media"
          radius={[8, 8, 2, 2]}
          isAnimationActive={false}
          maxBarSize={56}
          label={{ position: "top", fill: "var(--foreground)", fontSize: 12, fontWeight: 600 }}
        >
          {dados.map((d, i) => (
            <Cell key={i} fill={d.faixa ? COR[d.faixa] : "transparent"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
