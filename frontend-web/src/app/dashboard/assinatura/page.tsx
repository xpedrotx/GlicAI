"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, Check, Clock, CreditCard, ExternalLink, Gift, Lock, Minus, Sparkles, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Plano } from "@/lib/types";
import { Button, Card, CardTitulo, ErrorText, PageHeader, Skeleton } from "@/components/ui";
import { CheckoutEmbutido } from "@/components/checkout-embutido";

const BENEFICIOS = [
  { rotulo: "Registros de glicemia", free: "1 por dia", pro: "Ilimitados" },
  { rotulo: "Lembretes (basal, medições, remedição)", free: false, pro: true },
  { rotulo: "Cálculo de dose e alertas de hipo/hiper", free: true, pro: true },
  { rotulo: "Aviso aos cuidadores", free: true, pro: true },
  { rotulo: "Relatórios, PDF e painel web", free: true, pro: true },
];

type Checkout = { client_secret: string; publishable_key: string };

function formatarData(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

export default function AssinaturaPage() {
  const [plano, setPlano] = useState<Plano | null>(null);
  const [erro, setErro] = useState("");
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [abrindoCheckout, setAbrindoCheckout] = useState(false);
  const [abrindoPortal, setAbrindoPortal] = useState(false);
  const [aviso, setAviso] = useState<"sucesso" | "pendente" | null>(null);

  useEffect(() => {
    // Volta do checkout: ?sessao=cs_... — confirma no backend pra liberar o Pro na hora
    const sessao = new URLSearchParams(window.location.search).get("sessao");

    async function carregar() {
      try {
        if (sessao) {
          const r = await api.confirmarCheckout(sessao);
          setPlano(r);
          setAviso(r.status === "ok" ? "sucesso" : "pendente");
          window.history.replaceState(null, "", "/dashboard/assinatura");
          return;
        }
        setPlano(await api.plano());
      } catch {
        setErro("Não consegui carregar sua assinatura agora. Tenta de novo em instantes.");
      }
    }
    carregar();
  }, []);

  async function assinar() {
    setErro("");
    setAbrindoCheckout(true);
    try {
      setCheckout(await api.iniciarCheckout());
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui abrir o pagamento agora.");
    } finally {
      setAbrindoCheckout(false);
    }
  }

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
      <PageHeader titulo="Assinatura" descricao="Seu plano, pagamento e faturas." />

      {aviso === "sucesso" && (
        <div className="flex items-start gap-3 rounded-2xl border border-verde/30 bg-verde/10 px-5 py-4 text-sm">
          <BadgeCheck size={20} className="mt-0.5 shrink-0 text-verde" />
          <p>
            <span className="font-semibold">Pagamento confirmado!</span> O GlicAI Pro já está liberado na sua conta —
            registros ilimitados e lembretes de volta.
          </p>
        </div>
      )}
      {aviso === "pendente" && (
        <div className="flex items-start gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 text-sm">
          <Clock size={20} className="mt-0.5 shrink-0 text-accent" />
          <p>
            Ainda estamos aguardando a confirmação do pagamento. Isso pode levar alguns instantes — atualize a página em
            seguida.
          </p>
        </div>
      )}

      <ErrorText>{erro}</ErrorText>

      {!plano && !erro && <Skeleton className="h-[180px]" />}

      {plano && (
        <>
          <StatusDoPlano plano={plano} aoGerenciar={gerenciar} gerenciando={abrindoPortal} />

          {plano.plano !== "pro" && (
            <>
              <Comparativo plano={plano} />

              {checkout ? (
                <Card>
                  <CardTitulo
                    icone={<CreditCard size={18} />}
                    titulo="Pagamento"
                    descricao={`GlicAI Pro — ${plano.preco}. Cancele quando quiser.`}
                  />
                  <CheckoutEmbutido clientSecret={checkout.client_secret} publishableKey={checkout.publishable_key} />
                </Card>
              ) : (
                <Card className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-heading text-lg font-bold">GlicAI Pro — {plano.preco}</p>
                    <p className="mt-1 text-sm text-muted">
                      Pagamento seguro pelo Stripe, no cartão. Cancele quando quiser, sem multa.
                    </p>
                  </div>
                  {plano.pagamentos_disponiveis ? (
                    <Button onClick={assinar} carregando={abrindoCheckout} className="w-full sm:w-auto">
                      {!abrindoCheckout && <Sparkles size={16} />}
                      {abrindoCheckout ? "Abrindo..." : "Assinar agora"}
                    </Button>
                  ) : (
                    <p className="flex items-center gap-2 text-sm text-muted">
                      <TriangleAlert size={16} /> Pagamentos indisponíveis no momento.
                    </p>
                  )}
                </Card>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function StatusDoPlano({
  plano,
  aoGerenciar,
  gerenciando,
}: {
  plano: Plano;
  aoGerenciar: () => void;
  gerenciando: boolean;
}) {
  if (plano.plano === "pro") {
    return (
      <Card className="border-primary/30">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-white">
              <Sparkles size={20} />
            </span>
            <div>
              <p className="font-heading text-xl font-bold">GlicAI Pro</p>
              <p className="mt-0.5 text-sm text-muted">
                {plano.cortesia
                  ? "Cortesia — tudo liberado."
                  : plano.assinatura_status === "past_due"
                    ? "Não conseguimos cobrar sua última fatura. Atualize o cartão para não perder o acesso."
                    : plano.cancela_no_fim
                      ? `Assinatura cancelada — você tem acesso até ${formatarData(plano.renova_em)}.`
                      : plano.renova_em
                        ? `Renova em ${formatarData(plano.renova_em)} · ${plano.preco}`
                        : plano.preco}
              </p>
            </div>
          </div>
          {plano.tem_cliente_stripe && !plano.cortesia && (
            <Button variant="ghost" onClick={aoGerenciar} carregando={gerenciando}>
              {!gerenciando && <ExternalLink size={16} />}
              Gerenciar assinatura
            </Button>
          )}
        </div>
      </Card>
    );
  }

  if (plano.plano === "trial") {
    const dias = plano.dias_restantes_teste ?? 0;
    const pct = Math.max(4, Math.min(100, Math.round(((7 - dias + 1) / 7) * 100)));
    return (
      <Card>
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <Gift size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-heading text-xl font-bold">Teste grátis</p>
            <p className="mt-0.5 text-sm text-muted">
              {dias === 1 ? "Termina hoje" : `${dias} dias restantes`} · tudo liberado até{" "}
              {formatarData(plano.teste_termina_em)}
            </p>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-foreground/[0.07]">
              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface text-muted">
          <Lock size={20} />
        </span>
        <div>
          <p className="font-heading text-xl font-bold">Plano gratuito</p>
          <p className="mt-0.5 text-sm text-muted">
            Seu teste de 7 dias terminou. Você pode registrar {plano.medicoes_por_dia_free} medição por dia e não recebe
            lembretes. Assine para liberar tudo.
          </p>
        </div>
      </div>
    </Card>
  );
}

function Comparativo({ plano }: { plano: Plano }) {
  return (
    <Card className="p-0">
      <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-6 border-b border-border px-6 py-4 text-sm font-semibold">
        <span className="text-muted">Recursos</span>
        <span className="w-24 text-center">Gratuito</span>
        <span className="w-24 text-center text-primary">Pro · {plano.preco.replace("/mês", "")}</span>
      </div>
      {BENEFICIOS.map((b) => (
        <div
          key={b.rotulo}
          className="grid grid-cols-[1fr_auto_auto] items-center gap-x-6 border-b border-border px-6 py-3.5 text-sm last:border-0"
        >
          <span>{b.rotulo}</span>
          <Celula valor={b.free} />
          <Celula valor={b.pro} destaque />
        </div>
      ))}
    </Card>
  );
}

function Celula({ valor, destaque = false }: { valor: boolean | string; destaque?: boolean }) {
  return (
    <span className="flex w-24 justify-center">
      {typeof valor === "string" ? (
        <span className={`text-xs font-semibold ${destaque ? "text-primary" : "text-muted"}`}>{valor}</span>
      ) : valor ? (
        <Check size={18} className={destaque ? "text-primary" : "text-verde"} aria-label="Incluído" />
      ) : (
        <Minus size={18} className="text-muted" aria-label="Não incluído" />
      )}
    </span>
  );
}
