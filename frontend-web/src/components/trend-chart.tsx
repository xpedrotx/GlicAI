"use client";

import { useMemo, useState, useSyncExternalStore } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Glicemia, Perfil } from "@/lib/types";
import { formatarContexto, formatarData, formatarHorario } from "@/lib/clinico";
import { Segmentado } from "./ui";

/*
 * Medições de ponta de dedo são esparsas (3–6 por dia), então ligar ponto a
 * ponto com curva suavizada inventa picos e vales que nunca foram medidos.
 * Por isso: cada medição é um ponto colorido pela faixa, e a linha mostra só
 * a média de cada dia (tendência real). A visão "por horário" sobrepõe todos
 * os dias num dia de 24h, com a mediana e a faixa onde caem metade das
 * medições — mesma ideia do AGP (perfil glicêmico ambulatorial).
 */

type Faixa = "baixa" | "alvo" | "alta";
type Ponto = { x: number; valor: number; horario: string; contexto: string | null; faixa: Faixa };

const COR: Record<Faixa, string> = { baixa: "var(--vermelho)", alvo: "var(--verde)", alta: "var(--accent)" };
const ROTULO: Record<Faixa, string> = { baixa: "Abaixo do alvo", alvo: "No alvo", alta: "Acima do alvo" };

function faixaDe(valor: number, perfil: Perfil): Faixa {
  if (valor < perfil.limite_baixo) return "baixa";
  if (valor > perfil.limite_alto) return "alta";
  return "alvo";
}

function horaDoDia(iso: string, tz: string): number {
  const partes = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: false })
    .format(new Date(iso))
    .split(":");
  return (Number(partes[0]) % 24) + Number(partes[1]) / 60;
}

function percentil(ordenados: number[], p: number): number {
  const i = (ordenados.length - 1) * p;
  const a = Math.floor(i);
  const b = Math.ceil(i);
  return ordenados[a] + (ordenados[b] - ordenados[a]) * (i - a);
}

function Bolinha(props: { cx?: number; cy?: number; payload?: Ponto; r: number }) {
  const { cx, cy, payload, r } = props;
  if (cx == null || cy == null || !payload) return null;
  return <circle cx={cx} cy={cy} r={r} fill={COR[payload.faixa]} stroke="var(--card)" strokeWidth={1.5} />;
}

function Dica({
  active,
  payload,
  timezone,
}: {
  active?: boolean;
  payload?: { payload: Ponto | { media?: number; mediana?: number; x: number } }[];
  timezone: string;
}) {
  if (!active || !payload?.length) return null;
  const ponto = payload.map((p) => p.payload).find((p): p is Ponto => "faixa" in p);
  if (!ponto) return null;
  return (
    <div className="min-w-[160px] rounded-xl border border-border bg-card px-3.5 py-2.5 text-sm shadow-lg">
      <div className="flex items-baseline gap-1.5">
        <span className="font-heading text-lg font-bold" style={{ color: COR[ponto.faixa] }}>
          {ponto.valor}
        </span>
        <span className="text-xs text-muted">mg/dL</span>
      </div>
      <p className="text-xs font-medium" style={{ color: COR[ponto.faixa] }}>
        {ROTULO[ponto.faixa]}
      </p>
      <p className="mt-1.5 text-xs text-muted">{formatarHorario(ponto.horario, timezone)}</p>
      {ponto.contexto && ponto.contexto !== "outro" && (
        <p className="text-xs text-muted">{formatarContexto(ponto.contexto)}</p>
      )}
    </div>
  );
}

const MIN_POR_BLOCO = 3;

type Bloco = {
  x: number;
  rotulo: string;
  n: number;
  mediana: number;
  faixa: [number, number];
  faixaLarga: [number, number];
};

function DicaHorario({ active, payload }: { active?: boolean; payload?: { payload: Bloco | Ponto }[] }) {
  if (!active || !payload?.length) return null;
  const bloco = payload.map((p) => p.payload).find((p): p is Bloco => "mediana" in p);
  if (!bloco) return null;
  return (
    <div className="min-w-[190px] rounded-xl border border-border bg-card px-3.5 py-2.5 text-sm shadow-lg">
      <p className="text-xs font-semibold text-muted">{bloco.rotulo}</p>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="font-heading text-lg font-bold">{bloco.mediana}</span>
        <span className="text-xs text-muted">mg/dL de mediana</span>
      </div>
      <p className="mt-1 text-xs text-muted">
        Metade entre <span className="font-semibold text-foreground">{bloco.faixa[0]}</span> e{" "}
        <span className="font-semibold text-foreground">{bloco.faixa[1]}</span>
      </p>
      <p className="text-xs text-muted">{bloco.n} medições nesse horário</p>
    </div>
  );
}

function useTelaEstreita(): boolean {
  return useSyncExternalStore(
    (avisar) => {
      const mq = window.matchMedia("(max-width: 640px)");
      mq.addEventListener("change", avisar);
      return () => mq.removeEventListener("change", avisar);
    },
    () => window.matchMedia("(max-width: 640px)").matches,
    () => false
  );
}

export function TrendChart({ glicemias, perfil, timezone }: { glicemias: Glicemia[]; perfil: Perfil; timezone: string }) {
  const [modo, setModo] = useState<"linha" | "horario">("linha");
  const [mostrarPontos, setMostrarPontos] = useState(false);
  const estreita = useTelaEstreita();

  const dados = useMemo(() => {
    const pontos: Ponto[] = glicemias
      .map((g) => ({
        x: new Date(g.horario).getTime(),
        valor: g.valor,
        horario: g.horario,
        contexto: g.contexto,
        faixa: faixaDe(g.valor, perfil),
      }))
      .sort((a, b) => a.x - b.x);

    // média por dia (no fuso do paciente), posicionada ao meio-dia do dia
    const porDia = new Map<string, { soma: number; n: number; x: number }>();
    for (const p of pontos) {
      const dia = formatarData(p.horario, timezone);
      const d = porDia.get(dia) ?? { soma: 0, n: 0, x: p.x };
      d.soma += p.valor;
      d.n += 1;
      porDia.set(dia, d);
    }
    const mediasDiarias = [...porDia.values()].map((d) => ({ x: d.x, media: Math.round(d.soma / d.n) }));

    // visão por horário: todos os dias sobrepostos num dia de 24h
    const porHorario: Ponto[] = pontos.map((p) => ({ ...p, x: horaDoDia(p.horario, timezone) }));
    const blocos = new Map<number, number[]>();
    for (const p of porHorario) {
      const bloco = Math.floor(p.x / 2) * 2; // blocos de 2h
      blocos.set(bloco, [...(blocos.get(bloco) ?? []), p.valor]);
    }
    // blocos com poucas medições ficam de fora: 1 ou 2 valores não dizem
    // nada sobre "como costuma ser" aquele horário e entortariam a curva
    const perfilHorario: Bloco[] = [...blocos.entries()]
      .filter(([, vals]) => vals.length >= MIN_POR_BLOCO)
      .sort((a, b) => a[0] - b[0])
      .map(([bloco, vals]) => {
        const o = [...vals].sort((a, b) => a - b);
        const p = (q: number) => Math.round(percentil(o, q));
        return {
          x: bloco + 1,
          rotulo: `${String(bloco).padStart(2, "0")}h–${String(bloco + 2).padStart(2, "0")}h`,
          n: o.length,
          mediana: p(0.5),
          faixa: [p(0.25), p(0.75)],
          faixaLarga: [p(0.1), p(0.9)],
        };
      });

    const valores = pontos.map((p) => p.valor);
    const total = valores.length || 1;
    const tir = {
      baixa: Math.round((100 * pontos.filter((p) => p.faixa === "baixa").length) / total),
      alta: Math.round((100 * pontos.filter((p) => p.faixa === "alta").length) / total),
      alvo: 0,
    };
    tir.alvo = 100 - tir.baixa - tir.alta;

    const yMin = Math.max(0, Math.floor((Math.min(...valores, perfil.limite_baixo) - 15) / 10) * 10);
    const yMax = Math.ceil((Math.max(...valores, perfil.limite_alto) + 20) / 50) * 50;

    return { pontos, mediasDiarias, porHorario, perfilHorario, tir, yMin, yMax };
  }, [glicemias, perfil, timezone]);

  if (glicemias.length < 2) {
    return (
      <p className="py-10 text-center text-sm text-muted">
        São necessárias pelo menos 2 medições no período para mostrar o gráfico.
      </p>
    );
  }

  const { pontos, mediasDiarias, porHorario, perfilHorario, tir, yMin, yMax } = dados;
  const raio = (pontos.length > 150 ? 3 : pontos.length > 60 ? 4 : 5) * (estreita ? 0.65 : 1);
  // limites da faixa-alvo sempre aparecem; números redondos só se não ficarem
  // colados num limite (os rótulos se sobreporiam)
  const limites = [perfil.limite_baixo, perfil.limite_alto];
  const ticksY = [
    ...limites,
    ...[50, 250, 300, 350, 400, 450, 500].filter(
      (v) => v >= yMin && v <= yMax && limites.every((l) => Math.abs(v - l) > 25)
    ),
  ].sort((a, b) => a - b);

  const xMin = pontos[0].x;
  const xMax = pontos[pontos.length - 1].x;
  const ticksLinha = Array.from({ length: 6 }, (_, i) => xMin + ((xMax - xMin) * i) / 5);
  const curto = xMax - xMin < 2.5 * 24 * 3600 * 1000;

  const eixoComum = {
    stroke: "var(--muted)",
    fontSize: 12,
    axisLine: false,
    tickLine: false,
  } as const;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {modo === "linha" ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <Legenda cor={COR.alvo} texto={`No alvo (${perfil.limite_baixo}–${perfil.limite_alto})`} />
            <Legenda cor={COR.alta} texto="Acima" />
            <Legenda cor={COR.baixa} texto="Abaixo" />
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full bg-primary" />
              Média do dia
            </span>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full bg-primary" />
              Mediana
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-4 rounded-sm bg-primary/35" />
              Metade das medições
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-4 rounded-sm bg-primary/15" />8 em cada 10
            </span>
            <label className="flex cursor-pointer items-center gap-1.5 select-none">
              <input
                type="checkbox"
                checked={mostrarPontos}
                onChange={(e) => setMostrarPontos(e.target.checked)}
                className="h-3.5 w-3.5 accent-[var(--primary)]"
              />
              Mostrar medições
            </label>
          </div>
        )}
        <Segmentado
          opcoes={[
            { valor: "linha", rotulo: "Linha do tempo" },
            { valor: "horario", rotulo: "Por horário" },
          ]}
          valor={modo}
          aoMudar={setModo}
        />
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart margin={{ top: 10, right: 8, bottom: 0, left: -8 }}>
          <defs>
            <linearGradient id="gradienteAlvo" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--verde)" stopOpacity={0.16} />
              <stop offset="100%" stopColor="var(--verde)" stopOpacity={0.06} />
            </linearGradient>
          </defs>

          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
          <ReferenceArea y1={perfil.limite_baixo} y2={perfil.limite_alto} fill="url(#gradienteAlvo)" ifOverflow="hidden" />
          <ReferenceLine y={perfil.limite_alto} stroke="var(--accent)" strokeOpacity={0.5} strokeDasharray="5 5" />
          <ReferenceLine y={perfil.limite_baixo} stroke="var(--vermelho)" strokeOpacity={0.5} strokeDasharray="5 5" />

          {modo === "linha" ? (
            <XAxis
              {...eixoComum}
              dataKey="x"
              type="number"
              domain={[xMin, xMax]}
              ticks={ticksLinha}
              tickFormatter={(ts: number) =>
                curto
                  ? new Date(ts).toLocaleString("pt-BR", { timeZone: timezone, day: "2-digit", hour: "2-digit", minute: "2-digit" })
                  : formatarData(new Date(ts).toISOString(), timezone)
              }
              tickMargin={10}
              padding={{ left: 12, right: 12 }}
            />
          ) : (
            <XAxis
              {...eixoComum}
              dataKey="x"
              type="number"
              domain={[0, 24]}
              ticks={[0, 3, 6, 9, 12, 15, 18, 21, 24]}
              tickFormatter={(h: number) => `${String(h).padStart(2, "0")}h`}
              tickMargin={10}
            />
          )}
          <YAxis {...eixoComum} domain={[yMin, yMax]} ticks={ticksY} width={48} tickMargin={4} />

          {modo === "linha" ? (
            <Tooltip content={<Dica timezone={timezone} />} shared={false} cursor={false} />
          ) : (
            <Tooltip
              content={<DicaHorario />}
              cursor={{ stroke: "var(--muted)", strokeDasharray: "3 3", strokeOpacity: 0.6 }}
            />
          )}

          {modo === "linha" ? (
            <>
              <Line
                data={mediasDiarias}
                dataKey="media"
                type="monotoneX"
                stroke="var(--primary)"
                strokeWidth={2.5}
                strokeLinecap="round"
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
              <Scatter data={pontos} dataKey="valor" shape={<Bolinha r={raio} />} isAnimationActive={false} />
            </>
          ) : (
            <>
              <Area
                data={perfilHorario}
                dataKey="faixaLarga"
                type="monotoneX"
                fill="var(--primary)"
                fillOpacity={0.1}
                stroke="none"
                activeDot={false}
                isAnimationActive={false}
              />
              <Area
                data={perfilHorario}
                dataKey="faixa"
                type="monotoneX"
                fill="var(--primary)"
                fillOpacity={0.22}
                stroke="none"
                activeDot={false}
                isAnimationActive={false}
              />
              <Line
                data={perfilHorario}
                dataKey="mediana"
                type="monotoneX"
                stroke="var(--primary)"
                strokeWidth={2.5}
                dot={{ r: 3, fill: "var(--primary)", stroke: "var(--card)", strokeWidth: 1.5 }}
                activeDot={{ r: 5, fill: "var(--primary)", stroke: "var(--card)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
              {mostrarPontos && (
                <Scatter
                  data={porHorario}
                  dataKey="valor"
                  shape={<Bolinha r={raio * 0.7} />}
                  opacity={0.45}
                  isAnimationActive={false}
                />
              )}
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {modo === "horario" && (
        <p className="mt-1 text-center text-xs text-muted">
          {perfilHorario.length === 0
            ? "Ainda faltam medições para montar o perfil por horário — continue registrando."
            : `Todos os dias do período sobrepostos, em blocos de 2h. Horários com menos de ${MIN_POR_BLOCO} medições ficam de fora.`}
        </p>
      )}

      <div className="mt-6 border-t border-border pt-5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 text-xs">
          <span className="font-medium text-muted">Tempo no alvo</span>
          <span className="text-muted">meta recomendada: acima de 70%</span>
        </div>
        <div className="flex h-3 overflow-hidden rounded-full bg-foreground/[0.06]">
          {(["baixa", "alvo", "alta"] as Faixa[]).map((f) =>
            tir[f] > 0 ? (
              <div key={f} style={{ width: `${tir[f]}%`, background: COR[f] }} title={`${ROTULO[f]}: ${tir[f]}%`} />
            ) : null
          )}
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {(["baixa", "alvo", "alta"] as Faixa[]).map((f) => (
            <div key={f}>
              <p className="font-heading text-lg font-bold" style={{ color: COR[f] }}>
                {tir[f]}%
              </p>
              <p className="text-xs text-muted">{ROTULO[f]}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Legenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: cor }} />
      {texto}
    </span>
  );
}
