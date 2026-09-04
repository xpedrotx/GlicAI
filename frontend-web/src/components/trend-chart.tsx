"use client";

import {
  Label,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Glicemia, Perfil } from "@/lib/types";
import { classificarGlicemia, corParaCss, formatarData, formatarHorario } from "@/lib/clinico";

type Ponto = { ts: number; valor: number; horario: string };

// Espaço mínimo por ponto — com muitos pontos (ex: 72 em 30 dias) o gráfico
// vira um zigue-zague ilegível se espremido na largura da tela. Em vez
// disso, o gráfico cresce (com scroll horizontal) pra manter esse mínimo de
// espaçamento — `width: max(100%, Npx)` no JSX faz isso sem precisar medir
// o container: com poucos pontos, "100%" vence e preenche o card normal;
// com muitos, o valor em pixels vence e o gráfico fica mais largo que a
// tela. LARGURA_PARA_AVISAR_SCROLL só decide quando mostrar a dica de
// "arraste" — é uma estimativa (não sabemos a largura real do container
// aqui), por isso conservadora pra não acionar em telas maiores.
const PX_POR_PONTO = 14;
const LARGURA_PARA_AVISAR_SCROLL = 420;

function DotColorido(props: {
  cx?: number;
  cy?: number;
  payload?: Ponto;
  perfil: Perfil;
}) {
  const { cx, cy, payload, perfil } = props;
  if (cx == null || cy == null || !payload) return null;
  const { cor } = classificarGlicemia(payload.valor, perfil.limite_baixo, perfil.meta_glicemia, perfil.limite_alto);
  return <circle cx={cx} cy={cy} r={3} style={{ fill: corParaCss(cor) }} stroke="var(--card)" strokeWidth={1} />;
}

function TooltipPersonalizado({
  active,
  payload,
  timezone,
}: {
  active?: boolean;
  payload?: { payload: Ponto }[];
  timezone: string;
}) {
  if (!active || !payload?.length) return null;
  const ponto = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-md">
      <p className="font-semibold">{ponto.valor} mg/dL</p>
      <p className="text-muted">{formatarHorario(ponto.horario, timezone)}</p>
    </div>
  );
}

export function TrendChart({
  glicemias,
  perfil,
  timezone,
}: {
  glicemias: Glicemia[];
  perfil: Perfil;
  timezone: string;
}) {
  if (glicemias.length < 2) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        Precisa de pelo menos 2 medições no período pra mostrar a tendência.
      </p>
    );
  }

  const pontos: Ponto[] = glicemias
    .map((g) => ({ ts: new Date(g.horario).getTime(), valor: g.valor, horario: g.horario }))
    .sort((a, b) => a.ts - b.ts);

  const valores = pontos.map((p) => p.valor);
  const valorMin = Math.min(...valores, perfil.limite_baixo) - 10;
  const valorMax = Math.max(...valores, perfil.limite_alto) + 10;

  const larguraDesejada = pontos.length * PX_POR_PONTO;
  const rolavel = larguraDesejada > LARGURA_PARA_AVISAR_SCROLL;

  return (
    <div>
      <div className="overflow-x-auto overflow-y-hidden">
        <div style={{ width: `max(100%, ${larguraDesejada}px)` }}>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={pontos} margin={{ top: 20, right: 16, bottom: 4, left: 4 }}>
              <XAxis
                dataKey="ts"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(ts: number) => formatarData(new Date(ts).toISOString(), timezone)}
                stroke="var(--muted)"
                fontSize={12}
                tickMargin={8}
              />
              <YAxis
                domain={[valorMin, valorMax]}
                stroke="var(--muted)"
                fontSize={12}
                width={44}
                tickMargin={6}
              />
              <Tooltip content={<TooltipPersonalizado timezone={timezone} />} />

              <ReferenceLine y={perfil.limite_alto} stroke="var(--vermelho)" strokeDasharray="4 4" strokeOpacity={0.7}>
                <Label
                  value={`Alto ${perfil.limite_alto}`}
                  position="insideTopRight"
                  fill="var(--vermelho)"
                  fontSize={11}
                />
              </ReferenceLine>
              <ReferenceLine y={perfil.meta_glicemia} stroke="var(--foreground)" strokeDasharray="4 4" strokeOpacity={0.4}>
                <Label
                  value={`Meta ${perfil.meta_glicemia}`}
                  position="insideTopRight"
                  fill="var(--foreground)"
                  fontSize={11}
                />
              </ReferenceLine>
              <ReferenceLine y={perfil.limite_baixo} stroke="var(--vermelho)" strokeDasharray="4 4" strokeOpacity={0.7}>
                <Label
                  value={`Baixo ${perfil.limite_baixo}`}
                  position="insideBottomRight"
                  fill="var(--vermelho)"
                  fontSize={11}
                />
              </ReferenceLine>

              <Line
                type="monotone"
                dataKey="valor"
                stroke="var(--foreground)"
                strokeWidth={1.2}
                strokeOpacity={0.5}
                dot={<DotColorido perfil={perfil} />}
                activeDot={{ r: 5 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      {rolavel && <p className="mt-1 text-center text-xs text-muted">⟷ arraste pra ver o período completo</p>}
    </div>
  );
}
