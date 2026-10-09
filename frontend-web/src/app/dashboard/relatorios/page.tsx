"use client";

import { useEffect, useState } from "react";
import { Droplet } from "lucide-react";
import { api } from "@/lib/api";
import type { HbA1c, Padroes, Relatorio } from "@/lib/types";
import { Card, PageHeader, Segmentado, Skeleton, Vazio } from "@/components/ui";
import { BlocoHbA1c, BlocoPadroes, BlocoRelatorio } from "@/components/blocos-relatorio";

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
