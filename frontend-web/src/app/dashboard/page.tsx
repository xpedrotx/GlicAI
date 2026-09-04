"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Historico } from "@/lib/types";
import { classificarGlicemia, corParaCss, formatarContexto, formatarHorario } from "@/lib/clinico";
import { Card, StatCard } from "@/components/ui";
import { TrendChart } from "@/components/trend-chart";

const PERIODOS = [
  { dias: 7, rotulo: "7 dias" },
  { dias: 30, rotulo: "30 dias" },
  { dias: 90, rotulo: "90 dias" },
];

export default function DashboardPage() {
  const [dias, setDias] = useState(30);
  const [dados, setDados] = useState<Historico | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setCarregando(true);
    setErro("");
    api
      .historico(dias)
      .then(setDados)
      .catch(() => setErro("Não consegui carregar seu histórico agora. Tenta de novo."))
      .finally(() => setCarregando(false));
  }, [dias]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-heading text-2xl font-semibold">Histórico de glicemia</h1>
        <div className="flex gap-1 rounded-lg border border-border p-1">
          {PERIODOS.map((p) => (
            <button
              key={p.dias}
              onClick={() => setDias(p.dias)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                dias === p.dias ? "bg-primary text-primary-foreground" : "text-muted hover:text-foreground"
              }`}
            >
              {p.rotulo}
            </button>
          ))}
        </div>
      </div>

      {carregando && <p className="text-sm text-muted">Carregando...</p>}
      {erro && <p className="text-sm text-primary">{erro}</p>}

      {!carregando && !erro && dados && !dados.perfil && (
        <Card>
          <p className="text-sm text-muted">
            Ainda não achei seu perfil glicêmico — termina o cadastro pelo WhatsApp primeiro.
          </p>
        </Card>
      )}

      {!carregando && !erro && dados?.perfil && (
        <>
          <Resumo dados={dados} />

          <Card>
            <TrendChart glicemias={dados.glicemias} perfil={dados.perfil} timezone={dados.timezone ?? "America/Sao_Paulo"} />
          </Card>

          <TabelaGlicemias dados={dados} />
        </>
      )}
    </div>
  );
}

function Resumo({ dados }: { dados: Historico }) {
  const { glicemias, perfil } = dados;
  if (!perfil || glicemias.length === 0) {
    return (
      <Card>
        <p className="text-sm text-muted">Sem registros de glicemia nesse período.</p>
      </Card>
    );
  }

  const valores = glicemias.map((g) => g.valor);
  const media = valores.reduce((a, b) => a + b, 0) / valores.length;
  const naFaixa = valores.filter((v) => v >= perfil.limite_baixo && v <= perfil.limite_alto).length;
  const pctFaixa = Math.round((100 * naFaixa) / valores.length);
  const hipos = valores.filter((v) => v < perfil.limite_baixo).length;
  const hipers = valores.filter((v) => v > perfil.limite_alto).length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard rotulo="Medições" valor={String(valores.length)} />
      <StatCard rotulo="Média" valor={`${media.toFixed(0)} mg/dL`} />
      <StatCard rotulo="Na faixa" valor={`${pctFaixa}%`} corValor={pctFaixa >= 70 ? "var(--verde)" : undefined} />
      <StatCard
        rotulo="Hipo / Hiper"
        valor={`${hipos} / ${hipers}`}
        corValor={hipos + hipers > 0 ? "var(--vermelho)" : undefined}
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
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-5 py-3 font-medium">Data/hora</th>
              <th className="px-5 py-3 font-medium">mg/dL</th>
              <th className="px-5 py-3 font-medium">Contexto</th>
            </tr>
          </thead>
          <tbody>
            {ordenadas.length === 0 && (
              <tr>
                <td colSpan={3} className="px-5 py-6 text-center text-muted">
                  Sem registros nesse período.
                </td>
              </tr>
            )}
            {ordenadas.map((g, i) => {
              const { cor, seta } = classificarGlicemia(g.valor, perfil.limite_baixo, perfil.meta_glicemia, perfil.limite_alto);
              return (
                <tr key={i} className="border-b border-border last:border-0">
                  <td className="px-5 py-2.5 text-foreground/80">{formatarHorario(g.horario, tz)}</td>
                  <td className="px-5 py-2.5 font-semibold" style={{ color: corParaCss(cor) }}>
                    {g.valor} {seta}
                  </td>
                  <td className="px-5 py-2.5 text-foreground/80">{formatarContexto(g.contexto)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
