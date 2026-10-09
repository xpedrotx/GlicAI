"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock, Droplet, SlidersHorizontal, TriangleAlert, UserMinus, Utensils } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { HbA1c, Historico, Padroes, PerfilCompleto, Relatorio, ResumoPaciente } from "@/lib/types";
import { Button, Card, CardTitulo, ErrorText, PageHeader, Segmentado, Skeleton, Vazio } from "@/components/ui";
import { Legenda } from "@/components/graficos";
import { CarregandoPainel, VisaoGeralPaciente } from "@/components/painel-glicemia";
import { BlocoHbA1c, BlocoPadroes, BlocoRelatorio } from "@/components/blocos-relatorio";

type Aba = "geral" | "relatorios" | "perfil";

const ABAS = [
  { valor: "geral" as const, rotulo: "Visão geral" },
  { valor: "relatorios" as const, rotulo: "Relatórios" },
  { valor: "perfil" as const, rotulo: "Perfil de dose" },
];

const DIAS = 30;

export default function PacientePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [resumo, setResumo] = useState<ResumoPaciente | null>(null);
  const [naoAchou, setNaoAchou] = useState(false);
  const [aba, setAba] = useState<Aba>("geral");
  const [erro, setErro] = useState("");

  useEffect(() => {
    api
      .medicoPaciente(id)
      .then(setResumo)
      .catch(() => setNaoAchou(true));
  }, [id]);

  async function removerVinculo() {
    if (!window.confirm("Remover este paciente da sua lista? Você deixa de ver os dados dele (ele pode vincular de novo).")) return;
    try {
      await api.medicoDesvincular(id);
      router.push("/medico");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui remover agora.");
    }
  }

  if (naoAchou) {
    return (
      <Card className="max-w-xl">
        <Vazio
          icone={<TriangleAlert size={20} />}
          titulo="Paciente não encontrado"
          texto="Ele pode ter removido o acesso, ou o link está incorreto."
        />
        <div className="mt-2 text-center">
          <Link href="/medico" className="text-sm font-semibold text-primary hover:underline">
            Voltar para a lista
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Link href="/medico" className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-muted transition hover:text-foreground">
        <ArrowLeft size={15} /> Pacientes
      </Link>

      <PageHeader
        titulo={resumo ? (resumo.nome ?? "Paciente sem nome") : "Carregando..."}
        descricao={
          resumo
            ? `Vinculado em ${new Date(resumo.vinculado_em).toLocaleDateString("pt-BR")} · somente leitura`
            : undefined
        }
        acao={
          resumo && (
            <Button variant="ghost" onClick={removerVinculo}>
              <UserMinus size={16} /> Remover da lista
            </Button>
          )
        }
      />

      <ErrorText>{erro}</ErrorText>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmentado opcoes={ABAS} valor={aba} aoMudar={setAba} />
        {aba === "geral" && <Legenda />}
      </div>

      {aba === "geral" && <AbaGeral id={id} />}
      {aba === "relatorios" && <AbaRelatorios id={id} />}
      {aba === "perfil" && <AbaPerfil id={id} />}
    </div>
  );
}

function AbaGeral({ id }: { id: string }) {
  const [dados, setDados] = useState<Historico | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    api
      .medicoHistorico(id, DIAS)
      .then(setDados)
      .catch(() => setErro(true));
  }, [id]);

  if (erro) {
    return (
      <Card>
        <Vazio icone={<TriangleAlert size={20} />} titulo="Não consegui carregar os dados agora." />
      </Card>
    );
  }
  if (!dados) return <CarregandoPainel />;
  if (!dados.perfil) {
    return (
      <Card>
        <Vazio
          icone={<Droplet size={20} />}
          titulo="Esse paciente ainda não terminou o cadastro"
          texto="Quando ele completar o perfil pelo WhatsApp, os dados aparecem aqui."
        />
      </Card>
    );
  }
  return (
    <VisaoGeralPaciente
      dados={dados}
      dias={DIAS}
      textoSemDados="Esse paciente ainda não registrou glicemias nos últimos 30 dias."
      mostrarDoses
    />
  );
}

function AbaRelatorios({ id }: { id: string }) {
  const [periodo, setPeriodo] = useState<"semana" | "mes">("semana");
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [hba1c, setHba1c] = useState<HbA1c | null>(null);
  const [padroes, setPadroes] = useState<Padroes | null>(null);

  useEffect(() => {
    api.medicoRelatorio(id, periodo).then(setRelatorio).catch(() => {});
  }, [id, periodo]);

  useEffect(() => {
    api.medicoHba1c(id, 90).then(setHba1c).catch(() => {});
    api.medicoPadroes(id, 60).then(setPadroes).catch(() => {});
  }, [id]);

  return (
    <div className="flex flex-col gap-6">
      <Segmentado
        opcoes={[
          { valor: "semana" as const, rotulo: "Semana" },
          { valor: "mes" as const, rotulo: "Mês" },
        ]}
        valor={periodo}
        aoMudar={setPeriodo}
      />
      {!relatorio ? <Skeleton className="h-[260px]" /> : relatorio.perfil ? <BlocoRelatorio relatorio={relatorio} /> : (
        <Card>
          <Vazio icone={<Droplet size={20} />} titulo="Esse paciente ainda não terminou o cadastro" />
        </Card>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <BlocoHbA1c hba1c={hba1c} visaoMedico />
        <BlocoPadroes padroes={padroes} visaoMedico />
      </div>
    </div>
  );
}

function AbaPerfil({ id }: { id: string }) {
  const [dados, setDados] = useState<PerfilCompleto | null>(null);
  const [vazio, setVazio] = useState(false);

  useEffect(() => {
    api
      .medicoPerfil(id)
      .then(setDados)
      .catch(() => setVazio(true));
  }, [id]);

  if (vazio) {
    return (
      <Card>
        <Vazio icone={<Droplet size={20} />} titulo="Esse paciente ainda não terminou o cadastro" />
      </Card>
    );
  }
  if (!dados) return <Skeleton className="h-[360px]" />;

  const linhas: [string, string][] = [
    ["Meta", `${dados.meta_glicemia} mg/dL`],
    ["Limite baixo (hipoglicemia)", `${dados.limite_baixo} mg/dL`],
    ["Limite alto (hiperglicemia)", `${dados.limite_alto} mg/dL`],
    ["Fator de sensibilidade", `${dados.fator_sensibilidade} mg/dL por U`],
    ["Tempo de insulina ativa", dados.tempo_insulina_ativa_horas != null ? `${dados.tempo_insulina_ativa_horas} h` : "não configurado"],
  ];

  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <Card>
        <CardTitulo icone={<SlidersHorizontal size={18} />} titulo="Parâmetros" descricao="Usados no cálculo de dose do paciente." />
        <dl className="divide-y divide-border">
          {linhas.map(([r, v]) => (
            <div key={r} className="flex items-center justify-between py-3 text-sm first:pt-0 last:pb-0">
              <dt className="text-muted">{r}</dt>
              <dd className="font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <div className="flex flex-col gap-6">
        <Card>
          <CardTitulo icone={<Utensils size={18} />} titulo="Relação insulina:carboidrato" descricao="Gramas cobertas por 1 unidade, por período." />
          <Lista
            itens={dados.relacoes_ic.map((r) => ({
              rotulo: r.periodo,
              detalhe: `${r.hora_inicio}–${r.hora_fim}`,
              valor: `${r.gramas_por_unidade}g/U`,
            }))}
          />
        </Card>
        <Card>
          <CardTitulo icone={<Clock size={18} />} titulo="Insulina basal" descricao="Horários e doses diárias." />
          <Lista
            itens={dados.basal.map((b) => ({ rotulo: b.horario, detalhe: b.tipo_insulina ?? undefined, valor: `${b.dose}U` }))}
          />
        </Card>
        {dados.modificadores.length > 0 && (
          <Card>
            <CardTitulo icone={<SlidersHorizontal size={18} />} titulo="Modificadores de bolus" descricao="Ajustes aplicados quando ativos." />
            <Lista
              itens={dados.modificadores.map((m) => ({
                rotulo: m.nome,
                detalhe: m.ativo ? "Ativo" : "Inativo",
                valor: `${m.valor_ajuste >= 0 ? "+" : ""}${m.valor_ajuste}${m.tipo_ajuste === "percentual" ? "%" : "U"}`,
              }))}
            />
          </Card>
        )}
      </div>
    </div>
  );
}

function Lista({ itens }: { itens: { rotulo: string; detalhe?: string; valor: string }[] }) {
  if (itens.length === 0) return <p className="text-sm text-muted">Nada cadastrado.</p>;
  return (
    <ul className="divide-y divide-border">
      {itens.map((i, idx) => (
        <li key={idx} className="flex items-center justify-between py-3 text-sm first:pt-0 last:pb-0">
          <span>
            <span className="font-medium capitalize">{i.rotulo}</span>
            {i.detalhe && <span className="ml-2 text-muted">{i.detalhe}</span>}
          </span>
          <span className="rounded-lg bg-surface px-2.5 py-1 font-semibold">{i.valor}</span>
        </li>
      ))}
    </ul>
  );
}
