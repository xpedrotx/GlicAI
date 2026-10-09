"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, Check, CreditCard, ExternalLink, Sparkles, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Plano } from "@/lib/types";
import { Button, Card, ErrorText, PageHeader, Skeleton } from "@/components/ui";
import { FormularioCartao } from "@/components/formulario-cartao";

const BENEFICIOS = [
  "Registros de glicemia ilimitados no WhatsApp",
  "Lembretes de basal, medições e remedição",
  "Relatórios, gráficos e PDF para o médico",
  "Cancele quando quiser",
];

function formatarData(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

export default function AssinaturaPage() {
  const [plano, setPlano] = useState<Plano | null>(null);
  const [erro, setErro] = useState("");
  const [recemAssinou, setRecemAssinou] = useState(false);
  const [abrindoPortal, setAbrindoPortal] = useState(false);

  useEffect(() => {
    api
      .plano()
      .then(setPlano)
      .catch(() => setErro("Não consegui carregar sua assinatura agora. Tente de novo em instantes."));
  }, []);

  async function gerenciar() {
    setErro("");
    setAbrindoPortal(true);
    try {
      const { url } = await api.abrirPortal();
      window.location.href = url;
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui abrir o portal agora.");
      setAbrindoPortal(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Assinatura" descricao="Seu plano e pagamento." />

      {recemAssinou && (
        <div className="flex items-start gap-3 rounded-2xl border border-verde/30 bg-verde/10 px-5 py-4 text-sm">
          <BadgeCheck size={20} className="mt-0.5 shrink-0 text-verde" />
          <p>
            <span className="font-semibold">Pagamento confirmado!</span> O GlicAI Pro já está liberado: registros
            ilimitados e lembretes de volta.
          </p>
        </div>
      )}

      <ErrorText>{erro}</ErrorText>

      {!plano && !erro && <Skeleton className="h-[420px] max-w-2xl" />}

      {plano?.plano === "pro" && <CartaoPro plano={plano} aoGerenciar={gerenciar} gerenciando={abrindoPortal} />}

      {plano && plano.plano !== "pro" && (
        <Card className="w-full max-w-2xl border-primary/30">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-heading text-base font-bold text-primary">GlicAI Pro</p>
            {plano.plano === "trial" ? (
              <span className="rounded-full bg-accent/15 px-3 py-1 text-xs font-semibold text-accent">
                Teste grátis: {plano.dias_restantes_teste === 1 ? "termina hoje" : `${plano.dias_restantes_teste} dias restantes`}
              </span>
            ) : (
              <span className="rounded-full bg-surface px-3 py-1 text-xs font-semibold text-muted">
                Você está no plano gratuito
              </span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
            <p className="font-heading text-5xl font-extrabold tracking-tight">
              R$ 9,90<span className="text-lg font-medium text-muted"> /mês</span>
            </p>
            <p className="flex items-center gap-1.5 pb-1.5 text-sm text-muted">
              <CreditCard size={15} /> Por pessoa. Cartão de crédito.
            </p>
          </div>

          <ul className="mt-6 flex flex-col gap-2.5 text-[15px]">
            {BENEFICIOS.map((b) => (
              <li key={b} className="flex items-start gap-2.5">
                <Check size={18} className="mt-0.5 shrink-0 text-primary" />
                {b}
              </li>
            ))}
          </ul>

          <div className="mt-7 border-t border-border pt-7">
            {plano.pagamentos_disponiveis && plano.publishable_key ? (
              <FormularioCartao
                publishableKey={plano.publishable_key}
                preco="R$ 9,90/mês"
                aoConcluir={(novo) => {
                  setPlano(novo);
                  setRecemAssinou(true);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted">
                <TriangleAlert size={16} /> Pagamentos indisponíveis no momento.
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-col gap-2 text-xs leading-relaxed text-muted">
            {plano.plano === "trial" && (
              <p>Seu teste grátis termina em {formatarData(plano.teste_termina_em)}. A assinatura começa assim que você pagar.</p>
            )}
            <p>
              Os dados do cartão vão direto para o Stripe, dentro dos campos acima: o nosso servidor nunca vê o número do
              cartão. A cobrança é mensal e você cancela quando quiser, aqui mesmo.
            </p>
            <p>Seus dados de pagamento ficam com o Stripe. Aqui guardamos só o status da assinatura.</p>
          </div>
        </Card>
      )}
    </div>
  );
}

function CartaoPro({ plano, aoGerenciar, gerenciando }: { plano: Plano; aoGerenciar: () => void; gerenciando: boolean }) {
  const detalhe = plano.cortesia
    ? "Cortesia — tudo liberado."
    : plano.assinatura_status === "past_due"
      ? "Não conseguimos cobrar sua última fatura. Atualize o cartão para não perder o acesso."
      : plano.cancela_no_fim
        ? `Assinatura cancelada — você tem acesso até ${formatarData(plano.renova_em)}.`
        : plano.renova_em
          ? `Renova em ${formatarData(plano.renova_em)} · ${plano.preco}`
          : plano.preco;

  return (
    <Card className="w-full max-w-2xl border-primary/30">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-white">
            <Sparkles size={20} />
          </span>
          <div>
            <p className="font-heading text-xl font-bold">GlicAI Pro</p>
            <p className="mt-0.5 text-sm text-muted">{detalhe}</p>
          </div>
        </div>
        {plano.tem_cliente_stripe && !plano.cortesia && (
          <Button variant="ghost" onClick={aoGerenciar} carregando={gerenciando}>
            {!gerenciando && <ExternalLink size={16} />}
            Gerenciar assinatura
          </Button>
        )}
      </div>

      <ul className="mt-6 flex flex-col gap-2.5 border-t border-border pt-6 text-[15px]">
        {BENEFICIOS.map((b) => (
          <li key={b} className="flex items-start gap-2.5">
            <Check size={18} className="mt-0.5 shrink-0 text-primary" />
            {b}
          </li>
        ))}
      </ul>
    </Card>
  );
}
