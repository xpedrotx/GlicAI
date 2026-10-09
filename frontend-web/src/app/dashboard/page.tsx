"use client";

import { useEffect, useState } from "react";
import { Droplet, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useUsuario } from "@/lib/auth-context";
import type { Historico } from "@/lib/types";
import { Card, PageHeader, Vazio } from "@/components/ui";
import { Legenda } from "@/components/graficos";
import { CarregandoPainel, VisaoGeralPaciente } from "@/components/painel-glicemia";

// Visão geral sempre olha os últimos 30 dias (gráfico mensal) + o dia de hoje.
const DIAS = 30;

export default function DashboardPage() {
  const usuario = useUsuario();
  const [dados, setDados] = useState<Historico | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api
      .historico(DIAS)
      .then(setDados)
      .catch(() => setErro("Não consegui carregar seu histórico agora. Tenta de novo."))
      .finally(() => setCarregando(false));
  }, []);

  const primeiroNome = usuario?.nome?.trim().split(" ")[0];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo={primeiroNome ? `Olá, ${primeiroNome}` : "Visão geral"}
        descricao={`Seu dia de hoje e o resumo dos últimos ${DIAS} dias.`}
        acao={dados?.perfil ? <Legenda /> : undefined}
      />

      {carregando && <CarregandoPainel />}

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
        <VisaoGeralPaciente
          dados={dados}
          dias={DIAS}
          textoSemDados="Mande sua glicemia para o GlicAI no WhatsApp — ex: “tá 120” — e ela aparece aqui."
        />
      )}
    </div>
  );
}
