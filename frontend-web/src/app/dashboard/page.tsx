"use client";

import { useEffect, useState } from "react";
import { Activity, Droplet, Gauge, Target, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useUsuario } from "@/lib/auth-context";
import type { Historico } from "@/lib/types";
import { classificarGlicemia, corParaCss, formatarContexto, formatarData, formatarHorario } from "@/lib/clinico";
import { Card, CardTitulo, PageHeader, Segmentado, Skeleton, StatCard, Vazio } from "@/components/ui";
import { TrendChart } from "@/components/trend-chart";

const PERIODOS = [
  { valor: 7, rotulo: "7 dias" },
  { valor: 30, rotulo: "30 dias" },
  { valor: 90, rotulo: "90 dias" },
];

export default function DashboardPage() {
  const usuario = useUsuario();
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

  const primeiroNome = usuario?.nome?.trim().split(" ")[0];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo={primeiroNome ? `Olá, ${primeiroNome}` : "Visão geral"}
        descricao={`Seu resumo de glicemia dos últimos ${dias} dias.`}
        acao={<Segmentado opcoes={PERIODOS} valor={dias} aoMudar={setDias} />}
      />

      {carregando && <Carregando />}

      {erro && (
        <Card>
          <Vazio icone={<TriangleAlert size={20} />} titulo={erro} />
        </Card>
      )}

      {!carregando && !erro && dados && !dados.perfil && (
        <Card>
          <Vazio
            icone={<Droplet size={20} />}
            titulo="Seu perfil ainda não está completo"
            texto="Termine o cadastro pelo WhatsApp para começar a ver seus dados aqui."
          />
        </Card>
      )}

      {!carregando && !erro && dados?.perfil && (
        <>
          <Resumo dados={dados} />

          <Card>
            <CardTitulo
              icone={<Activity size={18} />}
              titulo="Tendência"
              descricao={`Faixa-alvo: ${dados.perfil.limite_baixo}–${dados.perfil.limite_alto} mg/dL · meta ${dados.perfil.meta_glicemia}`}
            />
            <TrendChart glicemias={dados.glicemias} perfil={dados.perfil} timezone={dados.timezone ?? "America/Sao_Paulo"} />
          </Card>

          <TabelaGlicemias dados={dados} />
        </>
      )}
    </div>
  );
}

function Carregando() {
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

function Resumo({ dados }: { dados: Historico }) {
  const { glicemias, perfil } = dados;
  if (!perfil || glicemias.length === 0) {
    return (
      <Card>
        <Vazio
          icone={<Droplet size={20} />}
          titulo="Sem glicemias nesse período"
          texto="Mande sua glicemia para o GlicAI no WhatsApp — ex: “tá 120” — e ela aparece aqui."
        />
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
      <StatCard
        rotulo="Média"
        valor={`${media.toFixed(0)}`}
        detalhe="mg/dL no período"
        icone={<Gauge size={17} />}
      />
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
